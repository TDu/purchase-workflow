# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import _, models
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _propagage_qty_to_moves(self):
        kit_line = self.env["purchase.order.line"].browse()
        for line in self:
            if line.product_id.bom_ids:
                kit_line |= line
                line._propagate_qty_to_moves_mrp()

        super(PurchaseOrderLine, self - kit_line)._propagage_qty_to_moves()

    def _propagate_qty_to_moves_mrp(self):
        self.ensure_one()
        # Take the first bom, how to know if it is the correct one ?
        #    There is _bom_find
        bom = self.product_id.bom_ids[0]
        if not bom:
            return
        new_kit_quantity = self.product_uom_qty
        # Get quantity done from mrp
        # WHY not used the qty done on the purchase line ?
        moves_done = self.move_ids.filtered(
            lambda move: move.state == "done" and not move.scrapped
        )
        filters = {
            "incoming_moves": lambda m: m.location_id.usage == "supplier"
            and (
                not m.origin_returned_move_id
                or (m.origin_returned_move_id and m.to_refund)
            ),
            "outgoing_moves": lambda m: m.location_id.usage != "supplier"
            and m.to_refund,
        }
        done_kit_quantity = moves_done._compute_kit_quantities(
            self.product_id, new_kit_quantity, bom, filters
        )
        if done_kit_quantity < new_kit_quantity:
            boms, bom_sub_lines = bom.explode(self.product_id, new_kit_quantity)
            for bom_line, bom_line_data in bom_sub_lines:
                bom_line_uom = bom_line.product_uom_id
                quant_uom = bom_line.product_id.uom_id
                # recreate dict of values since each child has its own bom_line_id
                # values = dict(procurement.values, bom_line_id=bom_line.id)
                component_qty, procurement_uom = bom_line_uom._adjust_uom_quantities(
                    bom_line_data["qty"], quant_uom
                )
                move = self.move_ids.filtered(
                    lambda move: move.product_id == bom_line.product_id
                    and move.state not in ("done", "cancel")
                )
                move.product_uom_qty = component_qty
        else:
            raise UserError(_("You cannot remove more that what remains to be done."))
