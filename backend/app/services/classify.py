import re

_CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    ("Teclados", re.compile(r"teclado|keyboard", re.I)),
    ("Ratones", re.compile(r"rat[oó]n|mouse", re.I)),
    ("Auriculares", re.compile(r"auricular|headset|cascos", re.I)),
    ("Alfombrillas", re.compile(r"alfombrilla|mouse ?pad", re.I)),
    ("Streaming", re.compile(r"micr[oó]fono|webcam|stream ?deck|capturadora", re.I)),
    (
        "Refrigeración",
        re.compile(r"refrigeraci[oó]n|l[ií]quida|ventilador|\baio\b|\bfans?\b", re.I),
    ),
    ("Fuentes", re.compile(r"fuente de alimentaci[oó]n|\bpsu\b|\b(rm|hx|cx|sf)\d{3,4}", re.I)),
    ("Memoria", re.compile(r"memoria|\bddr[45]\b|\bram\b", re.I)),
    ("Almacenamiento", re.compile(r"\bssd\b|nvme|disco", re.I)),
    ("Cajas", re.compile(r"\bcaja\b|torre|chasis|airflow|\b\d{4}[dx]\b", re.I)),
    ("Monitores", re.compile(r"monitor", re.I)),
    ("Sillas", re.compile(r"\bsilla", re.I)),
]


def categorize(title: str) -> str:
    for name, pattern in _CATEGORIES:
        if pattern.search(title):
            return name
    return "Otros"


def matches_brand(title: str, brand: str) -> bool:
    return re.search(rf"\b{re.escape(brand)}\b", title, re.I) is not None
