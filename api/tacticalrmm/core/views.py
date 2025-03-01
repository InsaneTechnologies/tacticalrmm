import os

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import ParseError
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework.views import APIView

from tacticalrmm.utils import notify_error

from .models import CodeSignToken, CoreSettings, CustomField, GlobalKVStore
from .serializers import (
    CodeSignTokenSerializer,
    CoreSettingsSerializer,
    CustomFieldSerializer,
    KeyStoreSerializer,
)


class UploadMeshAgent(APIView):
    parser_class = (FileUploadParser,)

    def put(self, request, format=None):
        if "meshagent" not in request.data and "arch" not in request.data:
            raise ParseError("Empty content")

        arch = request.data["arch"]
        f = request.data["meshagent"]
        mesh_exe = os.path.join(
            settings.EXE_DIR, "meshagent.exe" if arch == "64" else "meshagent-x86.exe"
        )
        with open(mesh_exe, "wb+") as j:
            for chunk in f.chunks():
                j.write(chunk)

        return Response(status=status.HTTP_201_CREATED)


@api_view()
def get_core_settings(request):
    settings = CoreSettings.objects.first()
    return Response(CoreSettingsSerializer(settings).data)


@api_view(["PATCH"])
def edit_settings(request):
    coresettings = CoreSettings.objects.first()
    serializer = CoreSettingsSerializer(instance=coresettings, data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response("ok")


@api_view()
def version(request):
    return Response(settings.APP_VER)


@api_view()
def dashboard_info(request):
    from tacticalrmm.utils import get_latest_trmm_ver

    return Response(
        {
            "trmm_version": settings.TRMM_VERSION,
            "latest_trmm_ver": get_latest_trmm_ver(),
            "dark_mode": request.user.dark_mode,
            "show_community_scripts": request.user.show_community_scripts,
            "dbl_click_action": request.user.agent_dblclick_action,
            "default_agent_tbl_tab": request.user.default_agent_tbl_tab,
            "client_tree_sort": request.user.client_tree_sort,
            "client_tree_splitter": request.user.client_tree_splitter,
            "loading_bar_color": request.user.loading_bar_color,
            "no_code_sign": hasattr(settings, "NOCODESIGN") and settings.NOCODESIGN,
        }
    )


@api_view()
def email_test(request):
    core = CoreSettings.objects.first()
    r = core.send_mail(
        subject="Test from Tactical RMM", body="This is a test message", test=True
    )

    if not isinstance(r, bool) and isinstance(r, str):
        return notify_error(r)

    return Response("Email Test OK!")


@api_view(["POST"])
def server_maintenance(request):
    from tacticalrmm.utils import reload_nats

    if "action" not in request.data:
        return notify_error("The data is incorrect")

    if request.data["action"] == "reload_nats":
        reload_nats()
        return Response("Nats configuration was reloaded successfully.")

    if request.data["action"] == "rm_orphaned_tasks":
        from agents.models import Agent
        from autotasks.tasks import remove_orphaned_win_tasks

        agents = Agent.objects.only("pk", "last_seen", "overdue_time", "offline_time")
        online = [i for i in agents if i.status == "online"]
        for agent in online:
            remove_orphaned_win_tasks.delay(agent.pk)

        return Response(
            "The task has been initiated. Check the Debug Log in the UI for progress."
        )

    if request.data["action"] == "prune_db":
        from logs.models import AuditLog, PendingAction

        if "prune_tables" not in request.data:
            return notify_error("The data is incorrect.")

        tables = request.data["prune_tables"]
        records_count = 0
        if "audit_logs" in tables:
            auditlogs = AuditLog.objects.filter(action="check_run")
            records_count += auditlogs.count()
            auditlogs.delete()

        if "pending_actions" in tables:
            pendingactions = PendingAction.objects.filter(status="completed")
            records_count += pendingactions.count()
            pendingactions.delete()

        if "alerts" in tables:
            from alerts.models import Alert

            alerts = Alert.objects.all()
            records_count += alerts.count()
            alerts.delete()

        return Response(f"{records_count} records were pruned from the database")

    return notify_error("The data is incorrect")


class GetAddCustomFields(APIView):
    def get(self, request):
        fields = CustomField.objects.all()
        return Response(CustomFieldSerializer(fields, many=True).data)

    def patch(self, request):
        if "model" in request.data.keys():
            fields = CustomField.objects.filter(model=request.data["model"])
            return Response(CustomFieldSerializer(fields, many=True).data)
        else:
            return notify_error("The request was invalid")

    def post(self, request):
        serializer = CustomFieldSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response("ok")


class GetUpdateDeleteCustomFields(APIView):
    def get(self, request, pk):
        custom_field = get_object_or_404(CustomField, pk=pk)

        return Response(CustomFieldSerializer(custom_field).data)

    def put(self, request, pk):
        custom_field = get_object_or_404(CustomField, pk=pk)

        serializer = CustomFieldSerializer(
            instance=custom_field, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response("ok")

    def delete(self, request, pk):
        get_object_or_404(CustomField, pk=pk).delete()

        return Response("ok")


class CodeSign(APIView):
    def get(self, request):
        token = CodeSignToken.objects.first()
        return Response(CodeSignTokenSerializer(token).data)

    def patch(self, request):
        import requests

        errors = []
        for url in settings.EXE_GEN_URLS:
            try:
                r = requests.post(
                    f"{url}/api/v1/checktoken",
                    json={"token": request.data["token"]},
                    headers={"Content-type": "application/json"},
                    timeout=15,
                )
            except Exception as e:
                errors.append(str(e))
            else:
                errors = []
                break

        if errors:
            return notify_error(", ".join(errors))

        if r.status_code == 400 or r.status_code == 401:  # type: ignore
            return notify_error(r.json()["ret"])  # type: ignore
        elif r.status_code == 200:  # type: ignore
            t = CodeSignToken.objects.first()
            if t is None:
                CodeSignToken.objects.create(token=request.data["token"])
            else:
                serializer = CodeSignTokenSerializer(instance=t, data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            return Response("Token was saved")

        try:
            ret = r.json()["ret"]  # type: ignore
        except:
            ret = "Something went wrong"
        return notify_error(ret)


class GetAddKeyStore(APIView):
    def get(self, request):
        keys = GlobalKVStore.objects.all()
        return Response(KeyStoreSerializer(keys, many=True).data)

    def post(self, request):
        serializer = KeyStoreSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response("ok")


class UpdateDeleteKeyStore(APIView):
    def put(self, request, pk):
        key = get_object_or_404(GlobalKVStore, pk=pk)

        serializer = KeyStoreSerializer(instance=key, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response("ok")

    def delete(self, request, pk):
        get_object_or_404(GlobalKVStore, pk=pk).delete()

        return Response("ok")
