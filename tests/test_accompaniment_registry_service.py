from datetime import date
from decimal import Decimal

from services.accompaniment_registry_service import (
    AccompanimentRegistryService,
)


def test_generate_dates_reserves_socialization_last_date() -> None:
    service = AccompanimentRegistryService()

    dates = service._generate_dates(  # noqa: SLF001
        date(2026, 9, 1),
        date(2026, 9, 10),
        ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"],
        3,
    )

    assert len(dates) == 4
    assert dates == sorted(dates)
    assert dates[-1] == date(2026, 9, 10)


def test_recalculate_assignments_preserves_resource_totals() -> None:
    service = AccompanimentRegistryService()
    draft = {
        "equipments": [
            {
                "id": "EQ1",
                "name": "Impresora 3D",
                "quantity_total": Decimal("32.00"),
                "value_total": Decimal("96000.00"),
            }
        ],
        "materials": [
            {
                "id": "MAT1",
                "name": "Filamento PETG",
                "quantity_total": Decimal("0.35"),
                "value_total": Decimal("32000.00"),
            }
        ],
        "activities": [
            {
                "uid": "a1",
                "title": "Modelado",
                "description": "Actividad",
                "type": "Acompanamiento",
                "other": "",
                "date": date(2026, 9, 1),
                "direct_hours": Decimal("0"),
                "indirect_hours": Decimal("8"),
                "equipment_ids": ["EQ1"],
                "material_ids": [],
                "is_socialization": False,
            },
            {
                "uid": "a2",
                "title": "Impresion",
                "description": "Actividad",
                "type": "Acompanamiento",
                "other": "",
                "date": date(2026, 9, 2),
                "direct_hours": Decimal("0"),
                "indirect_hours": Decimal("8"),
                "equipment_ids": ["EQ1"],
                "material_ids": ["MAT1"],
                "is_socialization": False,
            },
        ],
    }

    service.recalculate_assignments(draft)

    total_hours = sum(
        share.quantity
        for activity in draft["activities"]
        for share in activity["equipment_shares"]
    )
    total_wear = sum(
        share.value
        for activity in draft["activities"]
        for share in activity["equipment_shares"]
    )
    total_material = sum(
        share.quantity
        for activity in draft["activities"]
        for share in activity["material_shares"]
    )
    total_material_value = sum(
        share.value
        for activity in draft["activities"]
        for share in activity["material_shares"]
    )

    assert total_hours == Decimal("32.00")
    assert total_wear == Decimal("96000.00")
    assert total_material == Decimal("0.35")
    assert total_material_value == Decimal("32000.00")
    assert draft["activities"][0]["equipment_shares"][0].quantity == Decimal("16.00")
    assert draft["activities"][1]["equipment_shares"][0].quantity == Decimal("16.00")
    assert draft["activities"][0]["equipment_shares"][0].value == Decimal("48000.00")
    assert draft["activities"][1]["equipment_shares"][0].value == Decimal("48000.00")


def test_recalculate_assignments_assigns_material_to_one_activity() -> None:
    service = AccompanimentRegistryService()
    draft = {
        "equipments": [],
        "materials": [
            {
                "id": "MAT1",
                "name": "Resina",
                "quantity_total": Decimal("1.00"),
                "value_total": Decimal("45000.00"),
            }
        ],
        "activities": [
            {"uid": "a1", "equipment_ids": [], "material_ids": ["MAT1"]},
            {"uid": "a2", "equipment_ids": [], "material_ids": ["MAT1"]},
        ],
    }

    service.recalculate_assignments(draft)

    assert draft["activities"][0]["material_ids"] == ["MAT1"]
    assert draft["activities"][1]["material_ids"] == []
    share = draft["activities"][0]["material_shares"][0]
    assert share.quantity == Decimal("1.00")
    assert share.value == Decimal("45000.00")
