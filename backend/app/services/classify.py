import re

# El orden importa: gana la primera coincidencia (p. ej. "Portátil con teclado RGB" → Portátiles)
_CATEGORIES: list[tuple[str, str]] = [
    ("Portátiles", r"\bport[aá]til|laptop|notebook|chromebook|macbook"),
    (
        "Ordenadores",
        r"(pc|ordenador) (de )?(sobremesa|escritorio|gaming)|\bimac\b|\bmac (mini|studio|pro)\b",
    ),
    ("Tablets", r"\btablet|\bipad"),
    ("Wearables", r"smartwatch|reloj|pulsera de actividad|galaxy watch|apple watch|smartband"),
    ("Smartphones", r"smartphone|m[oó]vil|iphone|\bgalaxy [asz]\d"),
    ("Monitores", r"monitor|pantalla (secundaria|de apoyo|adicional)"),
    ("Televisores", r"\btv\b|televisor|smart tv|qled"),
    ("Teclados", r"teclado|keyboard"),
    ("Alfombrillas", r"alfombrilla|mouse ?pad"),  # antes que Ratones: "Alfombrilla de ratón"
    ("Ratones", r"rat[oó]n|mouse"),
    ("Auriculares", r"auricular|headset|cascos|earbuds|airpods|\bbuds"),
    ("Audio", r"altavoz|barra de sonido|soundbar|speaker|equipo de m[uú]sica"),
    ("Streaming", r"micr[oó]fono|webcam|stream ?deck|capturadora"),
    ("Fotografía", r"c[aá]mara|objetivo|gimbal|\bdron"),
    ("Consolas y gaming", r"consola|volante|\bmando\b|gamepad|joystick|playstation|nintendo|xbox"),
    # Antes que Componentes y Cajas: "Refrigerador CPU", "Refrigerador del chasis"
    (
        "Refrigeración",
        r"refrigera(ci[oó]n|nte|dor)|l[ií]quida|ventilador|\baio\b|\bfans?\b|hydro x|racor"
        r"|boquilla",
    ),
    ("Componentes", r"tarjeta gr[aá]fica|\b(rtx|gtx|rx) ?\d|placa base|procesador|\bcpu\b"),
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
    # Al final: "lámpara de escritorio" o "PC de escritorio" ya se han clasificado antes
    ("Escritorios", r"escritorio|\bmesa (gaming|de oficina|elevable)|\bdesk\b"),
]
_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in _CATEGORIES]


def categorize(title: str, description: str | None = None) -> str:
    for name, pattern in _COMPILED:
        if pattern.search(title):
            return name
    # Algunas tiendas (LDLC) titulan solo con el modelo y la descripción empieza por el
    # tipo de producto: "Auriculares para juegos - ... - compatible con móvil". Ahí gana
    # la coincidencia más temprana, no el orden de la lista.
    if description:
        hits = [(m.start(), name) for name, p in _COMPILED if (m := p.search(description))]
        if hits:
            return min(hits, key=lambda h: h[0])[1]
    return "Otros"


def matches_brand(title: str, brand: str) -> bool:
    return re.search(rf"\b{re.escape(brand)}\b", title, re.I) is not None
