# Copyright 2014-2016 Numérigraphe SARL
# Copyright 2017 Eficent Business and IT Consulting Services, S.L.
# Copyright 2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError
from odoo.tests.common import SavepointCase


class TestQtyUpdate(SavepointCase):
    at_install = False
    post_install = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.product_model = cls.env["product.product"]

        # Create products:
        cls.p1 = cls.product1 = cls.product_model.create(
            {"name": "Test Product 1", "type": "product", "default_code": "PROD1"}
        )
        p2 = cls.product2 = cls.product_model.create(
            {"name": "Test Product 2", "type": "product", "default_code": "PROD2"}
        )

        partner = cls.env["res.partner"].create({"name": "supplier"})
        cls.seller = partner

        # Create a kit
        cls.product_bed_with_curtain = cls.product_model.create(
            {
                "name": "BED WITH CURTAINS",
                "type": "product",
                "sale_ok": True,
                "purchase_ok": False,
            }
        )
        cls.tmpl_bed_with_curtain = cls.product_bed_with_curtain.product_tmpl_id
        cls.product_bed_structure = cls.product_model.create(
            {
                "name": "BED STRUCTURE",
                "type": "product",
                "sale_ok": True,
                "purchase_ok": True,
                "seller_ids": [(0, 0, {"name": cls.seller.id, "price": 50.0})],
                # "route_ids": [(4, cls.mto_route.id), (4, cls.buy_route.id)],
            }
        )
        cls.product_bed_curtain = cls.product_model.create(
            {
                "name": "BED CURTAIN",
                "type": "product",
                "sale_ok": True,
                "purchase_ok": True,
                "seller_ids": [(0, 0, {"name": cls.seller.id, "price": 10.0})],
                # "route_ids": [(4, cls.buy_route.id)],
            }
        )
        cls.bom_model = cls.env["mrp.bom"]
        cls.bom_bed_with_curtain = cls.bom_model.create(
            {
                "product_tmpl_id": cls.tmpl_bed_with_curtain.id,
                "product_id": cls.product_bed_with_curtain.id,
                "type": "phantom",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {"product_id": cls.product_bed_curtain.id, "product_qty": 2.0},
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_bed_structure.id,
                            "product_qty": 1.0,
                        },
                    ),
                ],
            }
        )

        cls.date_planned = "2020-04-30 12:00:00"
        cls.po = cls.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_bed_with_curtain.id,
                            "product_uom": cls.product_bed_with_curtain.uom_id.id,
                            "name": cls.product_bed_with_curtain.name,
                            "date_planned": cls.date_planned,
                            "product_qty": 42.0,
                            "price_unit": 300.0,
                        },
                    ),
                    # (
                    #     0,
                    #     0,
                    #     {
                    #         "product_id": cls.p1.id,
                    #         "product_uom": cls.p1.uom_id.id,
                    #         "name": cls.p1.name,
                    #         "date_planned": cls.date_planned,
                    #         "product_qty": 42.0,
                    #         "price_unit": 10.0,
                    #     },
                    # ),
                    # (
                    #     0,
                    #     0,
                    #     {
                    #         "product_id": p2.id,
                    #         "product_uom": p2.uom_id.id,
                    #         "name": p2.name,
                    #         "date_planned": cls.date_planned,
                    #         "product_qty": 12.0,
                    #         "price_unit": 10.0,
                    #     },
                    # ),
                    # (
                    #     0,
                    #     0,
                    #     {
                    #         "product_id": cls.p1.id,
                    #         "product_uom": cls.p1.uom_id.id,
                    #         "name": cls.p1.name,
                    #         "date_planned": cls.date_planned,
                    #         "product_qty": 1.0,
                    #         "price_unit": 10.0,
                    #     },
                    # ),
                ],
            }
        )
        cls.po.button_confirm()

    def _check_moves(self, moves, values):
        for move in moves:
            if move.state == "done":
                continue
            self.assertEqual(move.product_uom_qty, values[move.product_id])

    def _receive_kit(self, purchase_line, quantity_receive):
        move1 = purchase_line.move_ids.filtered(
            lambda r: r.product_id == self.product_bed_structure
        )
        new_move_vals = move1._split(quantity_receive)
        new_move_1 = self.env["stock.move"].create(new_move_vals)
        new_move_1._action_confirm(merge=False)
        new_move_1._action_assign()
        new_move_1.quantity_done = quantity_receive
        new_move_1._action_done()
        move2 = purchase_line.move_ids.filtered(
            lambda r: r.product_id == self.product_bed_curtain
        )
        new_move_vals = move2._split(quantity_receive * 2)
        new_move_2 = self.env["stock.move"].create(new_move_vals)
        new_move_2._action_confirm(merge=False)
        new_move_2._action_assign()
        new_move_2.quantity_done = quantity_receive * 2
        new_move_2._action_done()

    def test_purchase_line_qty_decrease_allowed(self):
        """"""
        line1 = self.po.order_line[0]
        moves = line1.move_ids
        line1.write({"product_qty": 30})
        self._check_moves(
            moves, {self.product_bed_structure: 30, self.product_bed_curtain: 60}
        )

    def test_purchase_line_qty_decrease_not_allowed(self):
        """"""
        line1 = self.po.order_line[0]
        self._receive_kit(line1, 30)
        moves = line1.move_ids
        self._check_moves(
            moves, {self.product_bed_structure: 12, self.product_bed_curtain: 24}
        )
        with self.assertRaises(UserError):
            line1.write({"product_qty": 30})

    # def test_purchase_line_unlink(self):
    #     """decrease qty on confirmed po -> decreased reception"""
    #     line1 = self.po.order_line[0]
    #     exception_regex = (
    #         r"Cannot delete a purchase order line which is in state 'purchase'."
    #     )
    #     with self.assertRaisesRegex(UserError, exception_regex):
    #         line1.unlink()

    # def test_purchase_line_qty_decrease_to_zero(self):
    #     """decrease qty on confirmed po -> decreased reception"""
    #     line1 = self.po.order_line[0]
    #     move1 = self.env["stock.move"].search([("purchase_line_id", "=", line1.id)])
    #     line1.write({"product_qty": 0})
    #     self.assertEqual(move1.product_uom_qty, 0)
    #     self.assertEqual(move1.state, "cancel")

    # def test_reduce_purchase_qty_with_canceled_moves(self):
    #     """Check canceled moves are not taken into account."""
    #     self.po.button_cancel()  # Cancel the moves
    #     self.po.button_draft()
    #     self.po.button_confirm()
    #     line1 = self.po.order_line[0]
    #     # One canceled move one ready
    #     self.assertEqual(len(line1.move_ids), 2)
    #     move_canceled = line1.move_ids.filtered_domain([("state", "=", "cancel")])
    #     move_assigned = line1.move_ids.filtered_domain([("state", "=", "assigned")])
    #     self.assertEqual(len(move_canceled), 1)
    #     self.assertEqual(len(move_assigned), 1)
    #     line1.write({"product_qty": 10})
    #     move = line1.move_ids.filtered(lambda r: r.state != "cancel")
    #     self.assertEqual(move.product_uom_qty, 10)

    # def test_reduce_purchase_qty_with_done_moves(self):
    #     """Check canceled moves are not taken into account."""
    #     self.po.button_draft()
    #     self.po.button_confirm()
    #     line1 = self.po.order_line[0]
    #     self.assertEqual(len(line1.move_ids), 1)
    #     # Receiving a partial qty (here we split the existing move by
    #     # convenience but we could generate a backorder as well)
    #     new_move_vals = line1.move_ids._split(10)
    #     new_move = line1.move_ids.create(new_move_vals)
    #     new_move._action_confirm(merge=False)
    #     new_move._action_assign()
    #     new_move.quantity_done = 10
    #     new_move._action_done()  # Receive 10/42 qties
    #     # Update the purchase order line to fit the received qty
    #     #   => the remaining 32 qties have to be canceled
    #     line1.write({"product_qty": 10})
    #     move_canceled = line1.move_ids.filtered_domain([("state", "=", "cancel")])
    #     move_done = line1.move_ids.filtered_domain([("state", "=", "done")])
    #     self.assertEqual(move_canceled.product_uom_qty, 32)
    #     self.assertEqual(move_done.product_uom_qty, 10)
    #     self.assertEqual(sum(line1.move_ids.mapped("product_uom_qty")), 42)
