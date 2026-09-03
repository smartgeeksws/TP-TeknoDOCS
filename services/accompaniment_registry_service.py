"""Logica local del modulo Registro de acompanamientos."""

from __future__ import annotations

import random
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


class AccompanimentRegistryError(RuntimeError):
    """Error controlado del modulo GCDTP-F-022."""


@dataclass(frozen=True)
class ResourceShare:
    id: str
    quantity: Decimal
    value: Decimal


class AccompanimentRegistryService:
    ALLOWED_TYPES = (
        "Accion de transferencia",
        "Acompanamiento",
        "Orientaciones",
        "Programa de fortalecimiento",
        "Otro",
    )
    PHASE_OPTIONS = ("Inicio", "Planeacion", "Ejecucion", "Cierre")
    WEEKDAY_OPTIONS = (
        ("Lunes", 0),
        ("Martes", 1),
        ("Miercoles", 2),
        ("Jueves", 3),
        ("Viernes", 4),
        ("Sabado", 5),
        ("Domingo", 6),
    )

    TECHNO_PARK = "Tecnoparque Nodo Angostura"
    REGIONAL_CENTER = (
        "Regional Huila - Centro de Formacion Agroindustrial La Angostura"
    )

    def build_resources(
        self,
        items: list[dict[str, Any]],
        *,
        prefix: str,
        quantity_key: str,
        value_key: str,
        quantity_label: str,
        value_label: str,
    ) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            name = str(item.get("name", "")).strip()
            quantity = self._decimal(item.get(quantity_key, 0))
            value = self._decimal(item.get(value_key, 0))
            if not name:
                raise AccompanimentRegistryError(
                    f"Completa el nombre del recurso {index} en {prefix}."
                )
            if quantity < 0 or value < 0:
                raise AccompanimentRegistryError(
                    f"Los valores de {name} deben ser mayores o iguales a cero."
                )
            resources.append(
                {
                    "id": f"{prefix}{index}",
                    "name": name,
                    "quantity_total": quantity,
                    "value_total": value,
                    "quantity_label": quantity_label,
                    "value_label": value_label,
                }
            )
        return resources

    def build_draft(
        self,
        *,
        project: dict[str, Any],
        form_data: dict[str, Any],
        generated: list[dict[str, Any]],
        equipments: list[dict[str, Any]],
        materials: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.validate_form_data(form_data)
        dates = self._generate_dates(
            form_data["phase_start_date"],
            form_data["phase_end_date"],
            form_data["worked_weekdays"],
            len(generated),
        )
        activities: list[dict[str, Any]] = []
        for index, item in enumerate(generated):
            activities.append(
                {
                    "uid": f"act_{index + 1}",
                    "title": item["title"],
                    "description": item["description"],
                    "type": item["type"],
                    "other": item["other"],
                    "date": dates[index],
                    "direct_hours": Decimal("0"),
                    "indirect_hours": Decimal("8"),
                    "equipment_ids": item["equipment_ids"],
                    "material_ids": item["material_ids"],
                    "is_socialization": False,
                }
            )
        activities.append(
            {
                "uid": "act_socialization",
                "title": "Socializacion de actividades y resultados desarrollados durante la fase del proyecto",
                "description": self._socialization_description(project, form_data["phase"]),
                "type": "Acompanamiento",
                "other": "",
                "date": dates[-1],
                "direct_hours": Decimal("3"),
                "indirect_hours": Decimal("0"),
                "equipment_ids": [],
                "material_ids": [],
                "is_socialization": True,
            }
        )
        draft = {
            "project_id": project["id"],
            "form_data": deepcopy(form_data),
            "equipments": deepcopy(equipments),
            "materials": deepcopy(materials),
            "activities": activities,
            "warnings": [],
        }
        self.recalculate_assignments(draft)
        return draft

    def recalculate_assignments(self, draft: dict[str, Any]) -> None:
        warnings: list[str] = []
        equipment_map = {item["id"]: item for item in draft["equipments"]}
        material_map = {item["id"]: item for item in draft["materials"]}
        for activity in draft["activities"]:
            activity["equipment_lines"] = []
            activity["material_lines"] = []
            activity["equipment_shares"] = []
            activity["material_shares"] = []

        for resource_id, resource in equipment_map.items():
            target_indexes = [
                index
                for index, activity in enumerate(draft["activities"])
                if resource_id in activity.get("equipment_ids", [])
            ]
            if not target_indexes:
                if resource["quantity_total"] > 0 or resource["value_total"] > 0:
                    warnings.append(
                        f"El equipo {resource['name']} no quedo asignado a ninguna actividad."
                    )
                continue
            shares = self._split_decimal(resource["quantity_total"], len(target_indexes), 2)
            values = self._split_decimal(resource["value_total"], len(target_indexes), 2)
            for index, quantity, value in zip(target_indexes, shares, values):
                activity = draft["activities"][index]
                activity["equipment_shares"].append(
                    ResourceShare(id=resource_id, quantity=quantity, value=value)
                )
                activity["equipment_lines"].append(
                    self._format_equipment_line(resource["name"], quantity, value)
                )

        for resource_id, resource in material_map.items():
            target_indexes = [
                index
                for index, activity in enumerate(draft["activities"])
                if resource_id in activity.get("material_ids", [])
            ]
            if not target_indexes:
                if resource["quantity_total"] > 0 or resource["value_total"] > 0:
                    warnings.append(
                        f"El material {resource['name']} no quedo asignado a ninguna actividad."
                    )
                continue
            target_index = target_indexes[0]
            if len(target_indexes) > 1:
                for duplicate_index in target_indexes[1:]:
                    duplicate = draft["activities"][duplicate_index]
                    duplicate["material_ids"] = [
                        item
                        for item in duplicate.get("material_ids", [])
                        if item != resource_id
                    ]
                warnings.append(
                    f"El material {resource['name']} se asigno completo a la primera actividad seleccionada."
                )
            activity = draft["activities"][target_index]
            activity["material_shares"].append(
                ResourceShare(
                    id=resource_id,
                    quantity=resource["quantity_total"],
                    value=resource["value_total"],
                )
            )
            activity["material_lines"].append(
                self._format_material_line(
                    resource["name"],
                    resource["quantity_total"],
                    resource["value_total"],
                )
            )
        draft["warnings"] = warnings

    def validate_form_data(self, form_data: dict[str, Any]) -> None:
        required = {
            "document_date": "fecha de elaboracion",
            "meeting_number": "numero de acta o reunion",
            "phase": "fase",
            "phase_start_date": "fecha de inicio de la fase",
            "phase_end_date": "fecha de finalizacion de la fase",
        }
        missing = [label for key, label in required.items() if not form_data.get(key)]
        if missing:
            raise AccompanimentRegistryError(
                "Completa los campos obligatorios: " + ", ".join(missing) + "."
            )
        if form_data["phase"] not in self.PHASE_OPTIONS:
            raise AccompanimentRegistryError("La fase seleccionada no es valida.")
        if form_data["phase_end_date"] < form_data["phase_start_date"]:
            raise AccompanimentRegistryError(
                "La fecha final de la fase no puede ser anterior a la fecha inicial."
            )
        if not form_data.get("worked_weekdays"):
            raise AccompanimentRegistryError(
                "Selecciona al menos un dia de trabajo para generar las fechas."
            )
        count = int(form_data.get("technical_activity_count", 0))
        if count <= 0:
            raise AccompanimentRegistryError(
                "La cantidad de actividades tecnicas debe ser mayor que cero."
            )

    def validate_project(self, project: dict[str, Any]) -> None:
        required = {
            "id": "id",
            "code": "codigo",
            "name": "nombre",
            "description": "descripcion",
            "expert": "experto asignado",
        }
        missing = [label for field, label in required.items() if not project.get(field)]
        if missing:
            raise AccompanimentRegistryError(
                "Faltan datos del proyecto activo: " + ", ".join(missing) + "."
            )

    def validate_draft(self, draft: dict[str, Any]) -> list[dict[str, Any]]:
        activities = draft.get("activities", [])
        if not activities:
            raise AccompanimentRegistryError("No hay actividades para generar el documento.")
        form_data = draft["form_data"]
        start = form_data["phase_start_date"]
        end = form_data["phase_end_date"]
        allowed_types = set(self.ALLOWED_TYPES)
        normalized: list[dict[str, Any]] = []
        for index, activity in enumerate(activities, start=1):
            if activity["type"] not in allowed_types:
                raise AccompanimentRegistryError(
                    f"El tipo de acompanamiento de la actividad {index} no es valido."
                )
            if activity["type"] == "Otro" and not str(activity.get("other", "")).strip():
                raise AccompanimentRegistryError(
                    f"La actividad {index} usa tipo Otro y requiere diligenciar el campo Otros."
                )
            activity_date = activity["date"]
            if activity_date < start or activity_date > end:
                raise AccompanimentRegistryError(
                    f"La fecha de la actividad {index} esta fuera del rango de la fase."
                )
            if self._decimal(activity["direct_hours"]) < 0 or self._decimal(activity["indirect_hours"]) < 0:
                raise AccompanimentRegistryError(
                    f"Las horas de la actividad {index} deben ser mayores o iguales a cero."
                )
            description = str(activity.get("description", "")).strip()
            if not description:
                raise AccompanimentRegistryError(
                    f"La descripcion de la actividad {index} no puede estar vacia."
                )
            normalized.append(activity)
        self._ensure_socialization_last(activities)
        self.recalculate_assignments(draft)
        self._validate_resource_totals(draft)
        draft["activities"] = sorted(
            activities,
            key=lambda item: (item["date"], 1 if item.get("is_socialization") else 0, item["title"]),
        )
        self._ensure_socialization_last(draft["activities"])
        return draft["activities"]

    def add_manual_activity(self, draft: dict[str, Any]) -> None:
        activities = draft["activities"]
        self._ensure_socialization_last(activities)
        insert_at = max(0, len(activities) - 1)
        activities.insert(
            insert_at,
            {
                "uid": f"act_manual_{len(activities)}",
                "title": "Nueva actividad",
                "description": "",
                "type": "Acompanamiento",
                "other": "",
                "date": draft["form_data"]["phase_start_date"],
                "direct_hours": Decimal("0"),
                "indirect_hours": Decimal("8"),
                "equipment_ids": [],
                "material_ids": [],
                "is_socialization": False,
            },
        )
        self.recalculate_assignments(draft)

    def remove_activity(self, draft: dict[str, Any], uid: str) -> None:
        draft["activities"] = [
            activity
            for activity in draft["activities"]
            if activity["uid"] != uid or activity.get("is_socialization")
        ]
        self._ensure_socialization_last(draft["activities"])
        self.recalculate_assignments(draft)

    def move_activity(self, draft: dict[str, Any], uid: str, direction: int) -> None:
        activities = draft["activities"]
        self._ensure_socialization_last(activities)
        position = next(
            (index for index, activity in enumerate(activities) if activity["uid"] == uid),
            None,
        )
        if position is None:
            return
        target = position + direction
        last_editable = len(activities) - 2 if activities and activities[-1].get("is_socialization") else len(activities) - 1
        if position < 0 or target < 0 or target > last_editable:
            return
        activities[position], activities[target] = activities[target], activities[position]
        self._ensure_socialization_last(activities)
        self.recalculate_assignments(draft)

    def export_filename(self, form_data: dict[str, Any], project_code: str, suffix: str) -> str:
        acta = self._safe_filename(str(form_data.get("meeting_number") or "sin-acta"))
        code = self._safe_filename(project_code or "sin-codigo")
        phase = self._safe_filename(str(form_data.get("phase") or "fase"))
        return f"GCDTP-F-022_Acta-{acta}_{code}_{phase}.{suffix}"

    def project_summary(self, project: dict[str, Any]) -> dict[str, str]:
        expert = project.get("expert") or {}
        return {
            "Codigo": project.get("code") or "N.A.",
            "Proyecto": project.get("name") or "N.A.",
            "Descripcion": project.get("description") or "N.A.",
            "Tecnoparque": self.TECHNO_PARK,
            "Regional y centro": self.REGIONAL_CENTER,
            "Experto responsable": expert.get("name") or "N.A.",
            "Linea tecnologica": project.get("technology_line") or "N.A.",
        }

    def _validate_resource_totals(self, draft: dict[str, Any]) -> None:
        for resource in draft["equipments"]:
            quantity = sum(
                share.quantity
                for activity in draft["activities"]
                for share in activity.get("equipment_shares", [])
                if share.id == resource["id"]
            )
            value = sum(
                share.value
                for activity in draft["activities"]
                for share in activity.get("equipment_shares", [])
                if share.id == resource["id"]
            )
            if quantity != resource["quantity_total"] or value != resource["value_total"]:
                raise AccompanimentRegistryError(
                    f"La distribucion del equipo {resource['name']} no coincide con sus totales."
                )
        for resource in draft["materials"]:
            quantity = sum(
                share.quantity
                for activity in draft["activities"]
                for share in activity.get("material_shares", [])
                if share.id == resource["id"]
            )
            value = sum(
                share.value
                for activity in draft["activities"]
                for share in activity.get("material_shares", [])
                if share.id == resource["id"]
            )
            if quantity != resource["quantity_total"] or value != resource["value_total"]:
                raise AccompanimentRegistryError(
                    f"La distribucion del material {resource['name']} no coincide con sus totales."
                )

    def _generate_dates(
        self,
        start: date,
        end: date,
        weekdays: list[str],
        technical_count: int,
    ) -> list[date]:
        weekday_numbers = {
            number
            for label, number in self.WEEKDAY_OPTIONS
            if label in weekdays
        }
        valid_dates = [
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
            if (start + timedelta(days=offset)).weekday() in weekday_numbers
        ]
        required = technical_count + 1
        if len(valid_dates) < required:
            raise AccompanimentRegistryError(
                "No hay suficientes fechas validas para las actividades y la socializacion. "
                "Amplia el rango, habilita mas dias o reduce actividades."
            )
        socialization_date = valid_dates[-1]
        pool = valid_dates[:-1]
        random_seed = f"{start.isoformat()}|{end.isoformat()}|{'-'.join(sorted(weekdays))}|{technical_count}"
        rng = random.Random(random_seed)
        chosen = sorted(rng.sample(pool, technical_count))
        chosen.append(socialization_date)
        return chosen

    @staticmethod
    def _socialization_description(project: dict[str, Any], phase: str) -> str:
        return (
            "Se realizo la socializacion tecnica de las actividades ejecutadas durante la "
            f"fase de {phase.lower()} del proyecto {project.get('name')}. Se presentaron "
            "avances, resultados, entregables y hallazgos relevantes, dejando claridad "
            "sobre el estado del componente trabajado y las acciones de continuidad."
        )

    @staticmethod
    def _split_decimal(total: Decimal, parts: int, decimals: int) -> list[Decimal]:
        if parts <= 0:
            return []
        quant = Decimal("1").scaleb(-decimals)
        if total == 0:
            return [Decimal("0").quantize(quant) for _ in range(parts)]
        base = (total / Decimal(parts)).quantize(quant, rounding=ROUND_HALF_UP)
        values = [base for _ in range(parts)]
        difference = total - sum(values)
        values[-1] = (values[-1] + difference).quantize(quant)
        return values

    @staticmethod
    def _format_equipment_line(name: str, hours: Decimal, value: Decimal) -> str:
        return (
            f"{name} - {AccompanimentRegistryService._format_decimal(hours)} h - "
            f"desgaste: ${AccompanimentRegistryService._format_currency(value)}"
        )

    @staticmethod
    def _format_material_line(name: str, quantity: Decimal, value: Decimal) -> str:
        return (
            f"{name} - {AccompanimentRegistryService._format_decimal(quantity)} - "
            f"valor: ${AccompanimentRegistryService._format_currency(value)}"
        )

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        normalized = value.quantize(Decimal("0.01")).normalize()
        text = format(normalized, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text.replace(".", ",")

    @staticmethod
    def _format_currency(value: Decimal) -> str:
        quantized = value.quantize(Decimal("0.01"))
        text = f"{quantized:,.2f}"
        return text.replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))

    @staticmethod
    def _safe_filename(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
        return cleaned.strip("_") or "documento"

    @staticmethod
    def _ensure_socialization_last(activities: list[dict[str, Any]]) -> None:
        socializations = [
            activity for activity in activities if activity.get("is_socialization")
        ]
        others = [activity for activity in activities if not activity.get("is_socialization")]
        activities[:] = others + socializations
