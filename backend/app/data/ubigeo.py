"""Official INEI UBIGEO hierarchy distributed by CONCYTEC."""

import csv
from functools import lru_cache
from pathlib import Path


@lru_cache
def locations() -> list[dict[str, str]]:
    source = Path(__file__).with_name("ubigeo_inei.csv")
    # The CONCYTEC export uses the Latin-1 encoding used by the source CSV.
    with source.open(encoding="latin-1") as file:
        rows = csv.DictReader(file)
        return [
            {
                "department_code": row["cod_dep_inei"],
                "department_name": row["desc_dep_inei"],
                "province_code": row["cod_prov_inei"],
                "province_name": row["desc_prov_inei"],
                "ubigeo": row["cod_ubigeo_inei"],
                "district_name": row["desc_ubigeo_inei"],
            }
            for row in rows
            if row["cod_ubigeo_inei"].isdigit() and len(row["cod_ubigeo_inei"]) == 6
        ]


@lru_cache
def location_by_ubigeo() -> dict[str, dict[str, str]]:
    return {location["ubigeo"]: location for location in locations()}


def location_hierarchy() -> list[dict]:
    departments: dict[str, dict] = {}
    for location in locations():
        department = departments.setdefault(
            location["department_code"],
            {"code": location["department_code"], "name": location["department_name"], "provinces": {}},
        )
        province = department["provinces"].setdefault(
            location["province_code"],
            {"code": location["province_code"], "name": location["province_name"], "districts": []},
        )
        province["districts"].append(
            {"code": location["ubigeo"], "name": location["district_name"]},
        )
    return [
        {
            "code": department["code"],
            "name": department["name"],
            "provinces": [
                {**province, "districts": sorted(province["districts"], key=lambda district: district["name"])}
                for province in sorted(department["provinces"].values(), key=lambda province: province["name"])
            ],
        }
        for department in sorted(departments.values(), key=lambda department: department["name"])
    ]
