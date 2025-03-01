<template>
  <div>
    <div class="row">
      <div class="text-subtitle2">Global Key Store</div>
      <q-space />
      <q-btn size="sm" color="grey-5" icon="fas fa-plus" text-color="black" label="Add key" @click="addKey" />
    </div>
    <hr />
    <q-table
      dense
      :data="keystore"
      :columns="columns"
      :pagination.sync="pagination"
      row-key="id"
      binary-state-sort
      hide-pagination
      virtual-scroll
      :rows-per-page-options="[0]"
      no-data-label="No Keys added yet"
    >
      <!-- body slots -->
      <template v-slot:body="props">
        <q-tr :props="props" class="cursor-pointer" @dblclick="editKey(props.row)">
          <!-- context menu -->
          <q-menu context-menu>
            <q-list dense style="min-width: 200px">
              <q-item clickable v-close-popup @click="editKey(props.row)">
                <q-item-section side>
                  <q-icon name="edit" />
                </q-item-section>
                <q-item-section>Edit</q-item-section>
              </q-item>
              <q-item clickable v-close-popup @click="deleteKey(props.row)">
                <q-item-section side>
                  <q-icon name="delete" />
                </q-item-section>
                <q-item-section>Delete</q-item-section>
              </q-item>

              <q-separator></q-separator>

              <q-item clickable v-close-popup>
                <q-item-section>Close</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
          <!-- name -->
          <q-td>
            {{ props.row.name }}
          </q-td>
          <!-- value -->
          <q-td>
            {{ props.row.value }}
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>

<script>
import KeyStoreForm from "@/components/modals/coresettings/KeyStoreForm";
import mixins from "@/mixins/mixins";

export default {
  name: "KeyStoreTable",
  mixins: [mixins],
  data() {
    return {
      keystore: [],
      pagination: {
        rowsPerPage: 0,
        sortBy: "name",
        descending: true,
      },
      columns: [
        {
          name: "name",
          label: "Name",
          field: "name",
          align: "left",
          sortable: true,
        },
        {
          name: "value",
          label: "Value",
          field: "value",
          align: "left",
          sortable: true,
        },
      ],
    };
  },
  methods: {
    getKeyStore() {
      this.$q.loading.show();

      this.$axios
        .get("/core/keystore/")
        .then(r => {
          this.$q.loading.hide();
          this.keystore = r.data;
        })
        .catch(e => {
          this.$q.loading.hide();
        });
    },
    addKey() {
      this.$q
        .dialog({
          component: KeyStoreForm,
          parent: this,
        })
        .onOk(() => {
          this.getKeyStore();
        });
    },
    editKey(key) {
      this.$q
        .dialog({
          component: KeyStoreForm,
          parent: this,
          globalKey: key,
        })
        .onOk(() => {
          this.getKeyStore();
        });
    },
    deleteKey(key) {
      this.$q
        .dialog({
          title: `Delete key: ${key.name}?`,
          cancel: true,
          ok: { label: "Delete", color: "negative" },
        })
        .onOk(() => {
          this.$q.loading.show();
          this.$axios
            .delete(`/core/keystore/${key.id}/`)
            .then(r => {
              this.getKeyStore();
              this.$q.loading.hide();
              this.notifySuccess(`key: ${key.name} was deleted!`);
            })
            .catch(error => {
              this.$q.loading.hide();
              this.notifyError(`An Error occured while deleting key: ${key.name}`);
            });
        });
    },
  },
  mounted() {
    this.getKeyStore();
  },
};
</script>