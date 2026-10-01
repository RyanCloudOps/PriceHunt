import re

# El orden importa: gana la primera coincidencia (p. ej. "Portátil con teclado RGB" → Portátiles)
_CATEGORIES: list[tuple[str, str]] = [
    ("Portátiles", r"port[aá]til|laptop|notebook|chromebook"),
    ("Tablets", r"\btablet|\bipad"),
    ("Wearables", r"smartwatch|reloj|pulsera de actividad|galaxy watch|smartband"),
    ("Smartphones", r"smartphone|m[oó]vil|iphone|\bgalaxy [asz]\d"),
    ("Monitores", r"monitor"),
    ("Televisores", r"\btv\b|televisor|smart tv|qled"),
    ("Teclados", r"teclado|keyboard"),
    ("Ratones", r"rat[oó]n|mouse"),
    ("Auriculares", r"auricular|headset|cascos|earbuds|airpods|\bbuds"),
    ("Audio", r"altavoz|barra de sonido|soundbar|speaker|equipo de m[uú]sica"),
    ("Alfombrillas", r"alfombrilla|mouse ?pad"),
    ("Streaming", r"micr[oó]fono|webcam|stream ?deck|capturadora"),
    ("Fotografía", r"c[aá]mara|objetivo|gimbal|\bdron"),
    ("Consolas y gaming", r"consola|volante|\bmando\b|gamepad|joystick|playstation|nintendo|xbox"),
    ("Componentes", r"tarjeta gr[aá]fica|\b(rtx|gtx|rx) ?\d|placa base|procesador|\bcpu\b"),
    ("Refrigeración", r"refrigeraci[oó]n|l[ií]quida|ventilador|\baio\b|\bfans?\b"),
    ("Fuentes", r"fuente de alimentaci[oó]n|\bpsu\b|\b(rm|hx|cx|sf)\d{3,4}"),
    ("Memoria", r"memoria|\bddr[45]\b|\bram\b"),
    ("Almacenamiento", r"\bssd\b|nvme|disco|pendrive|tarjeta (de memoria|micro ?sd)"),
    ("Cajas", r"\bcaja\b|torre|chasis|airflow|\b\d{4}[dx]\b"),
    ("Sillas", r"\bsilla"),
    ("Impresoras", r"impresora|multifunci[oó]n|esc[aá]ner"),
    ("Redes", r"router|\bwi-?fi\b|\bmesh\b|repetidor|switch de red"),
    (
        "Electrodomésticos",
        r"lavadora|secadora|frigor[ií]fico|nevera|horno|microondas|lavavajillas|aspirador"
        r"|placa (de )?inducci[oó]n|vitrocer[aá]mica|cafetera|freidora|aire acondicionado",
    ),
    ("Iluminación", r"l[aá]mpara|iluminaci[oó]n|tira led|bombilla|\blight\b"),
]
_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in _CATEGORIES]


def categorize(title: str) -> str:
    for name, pattern in _COMPILED:
        if pattern.search(title):
            return name
    return "Otros"


def matches_brand(title: str, brand: str) -> bool:
    return re.search(rf"\b{re.escape(brand)}\b", title, re.I) is not None
