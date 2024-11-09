/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";

class EventModalFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");

        onMounted(() => {
            setTimeout(() => this.notifyEventRead(), 100);
        });
    }

    async notifyEventRead() {
        try {
            const record = this.model.root;
            const recordData = record.data;

            // Usar session.uid directamente
            const currentUserId = session.storeData?.['res.partner']?.[1]?.userId;
            console.log('session', session)

            console.log("Datos completos del registro:", recordData);
            console.log("ID del Evento:", recordData.id || record.resId);
            console.log("ID del usuario actual:", currentUserId);

            const eventId = recordData.id || record.resId;
            if (!eventId) {
                console.log("No hay ID de evento disponible");
                return;
            }

            if (!currentUserId) {
                console.log("No se puede identificar al usuario actual");
                return;
            }

            if (recordData.state === 'cancelled') {
                console.log("Evento cancelado, no se procesa");
                return;
            }

            console.log('Antes de result')
            const result = await this.orm.call(
                'academy.event',
                'notify_event_read',
                [[eventId]],
                {
                    user_id: currentUserId,
                }
            );

            console.log('Después de result')
            if (result) {
                this.notification.add(
                    "Evento marcado como leído",
                    {type: "success", sticky: false}
                );
                await record.load();
            }

        } catch (error) {
            console.error("Error detallado:", error);
            this.notification.add(
                `Error al marcar como leído: ${error.message || error.data?.message || 'Error desconocido'}`,
                {type: "warning", sticky: true}
            );
        }
    }
}

registry.category("views").add("event_modal_form", {
    ...formView,
    Controller: EventModalFormController,
});