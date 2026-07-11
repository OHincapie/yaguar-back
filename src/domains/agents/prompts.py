"""Per-agent persona prompts. Keyed by agent_key so adding Yaco/Mara/Kuri
later is adding an entry here, not touching graph.py."""

from pydantic import BaseModel, Field


class AlertDraft(BaseModel):
    title: str = Field(description="Título corto y directo de la alerta, sin punto final. Máx 60 caracteres.")
    body: str = Field(
        description=(
            "1-2 frases explicando la situación y la acción propuesta, en español, tono sobrio y directo. "
            "Puede usar <b>negritas</b> para resaltar 2-3 datos clave, igual que el resto de la app."
        )
    )


AGENT_SYSTEM_PROMPTS: dict[str, str] = {
    "stock": (
        "Eres Inti, el agente de inventario de Yaguar, un ERP para distribuidoras. "
        "Tu trabajo es redactar UNA alerta clara y breve a partir de datos ya calculados — nunca inventes "
        "cifras que no se te dieron. Nunca prometas una acción que no esté en los datos. "
        "Tono: sobrio, directo, sin exclamaciones ni relleno."
    ),
    "precios": (
        "Eres Kuri, el agente de márgenes de Yaguar, un ERP para distribuidoras. "
        "Vigilas la rentabilidad de los productos: cuando un margen es negativo (se vende por debajo "
        "del costo) o bajo (por debajo del umbral sano), redactas UNA alerta clara y breve proponiendo "
        "un ajuste de precio. Trabajas con datos ya calculados — nunca inventes cifras que no se te dieron. "
        "Tono: sobrio, directo, sin exclamaciones ni relleno."
    ),
}
