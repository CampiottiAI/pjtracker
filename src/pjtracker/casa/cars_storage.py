"""Persistence for household cars (JSON under data/casa/)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NotRequired, TypedDict

from pjtracker.casa import storage as casa_storage


class Car(TypedDict):
    id: str
    name: str
    placa: NotRequired[str | None]
    modelo: NotRequired[str | None]


def cars_path() -> Path:
    return casa_storage.CASA_DATA_DIR / "cars.json"


def _ensure_data_dir() -> None:
    cars_path().parent.mkdir(parents=True, exist_ok=True)


def load_cars() -> list[Car]:
    _ensure_data_dir()
    path = cars_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Car(c) for c in data]


def save_cars(cars: list[Car]) -> None:
    _ensure_data_dir()
    cars_path().write_text(
        json.dumps([dict(c) for c in cars], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_car(car_id: str) -> Car | None:
    for c in load_cars():
        if c["id"] == car_id:
            return c
    return None


def slug_from_name(name: str) -> str:
    s = name.strip().lower()
    for old, new in [
        ("á", "a"),
        ("à", "a"),
        ("ã", "a"),
        ("â", "a"),
        ("é", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ô", "o"),
        ("õ", "o"),
        ("ú", "u"),
        ("ç", "c"),
    ]:
        s = s.replace(old, new)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s or "carro"


def add_car(
    car_id: str,
    name: str,
    *,
    placa: str | None = None,
    modelo: str | None = None,
) -> Car:
    cars = load_cars()
    if any(c["id"] == car_id for c in cars):
        raise ValueError(f"Car id already exists: {car_id}")
    car = Car({"id": car_id, "name": name, "placa": placa, "modelo": modelo})
    cars.append(car)
    save_cars(cars)
    return car


def update_car(
    car_id: str,
    *,
    name: str | None = None,
    placa: str | None = None,
    modelo: str | None = None,
) -> Car | None:
    cars = load_cars()
    for i, c in enumerate(cars):
        if c["id"] == car_id:
            updated = dict(c)
            if name is not None:
                updated["name"] = name
            if placa is not None:
                updated["placa"] = placa or None
            if modelo is not None:
                updated["modelo"] = modelo or None
            cars[i] = Car(updated)
            save_cars(cars)
            return cars[i]
    return None


def remove_car(car_id: str) -> None:
    cars = [c for c in load_cars() if c["id"] != car_id]
    save_cars(cars)


def car_label(car: Car) -> str:
    parts = [car["name"]]
    placa = car.get("placa")
    modelo = car.get("modelo")
    if placa:
        parts.append(placa)
    elif modelo:
        parts.append(modelo)
    return " · ".join(parts)
