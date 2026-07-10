-- Costo en USD del uso de IA, calculado desde ai_usage_events.
--
-- La tabla guarda deliberadamente tokens crudos y NO dólares: los precios
-- por token cambian, y grabar un costo fijo en cada fila significaría quedar
-- desactualizado cada vez que OpenAI los mueva. El costo se calcula aquí,
-- al consultar, contra la tabla de precios de abajo.
--
-- ⚠️ PRECIOS: actualizados a 2026-07 (USD por 1 millón de tokens). Antes de
-- tomar decisiones con estos números, verifícalos en
-- https://platform.openai.com/docs/pricing — gpt-5-mini ya no aparece en la
-- tabla principal (es legacy); estos son los precios con los que se contrató.
-- Para cambiar un precio solo edita el VALUES de este CTE.
--
-- Cómo correrla: en el SQL editor de Neon (console.neon.tech), o
--   psql "$DATABASE_URL" -f queries/ai_usage_cost.sql

WITH pricing (model_prefix, input_usd, cached_input_usd, output_usd) AS (
  VALUES
    -- gpt-5-mini y sus variantes con fecha (gpt-5-mini-2025-08-07, usado
    -- por los agentes LangGraph del backend)
    ('gpt-5-mini',              0.25, 0.025, 2.00),
    -- Transcripción de notas de voz. Se factura por tokens de audio de
    -- entrada + tokens de texto de salida (~USD 0.003/minuto de audio).
    ('gpt-4o-mini-transcribe',  1.25, NULL,  5.00)
),
costed AS (
  SELECT
    e.source,
    e.model,
    date_trunc('month', e.created_at) AS month,
    e.input_tokens,
    e.cached_input_tokens,
    e.output_tokens,
    -- Los tokens cacheados vienen incluidos dentro de input_tokens, por eso
    -- se restan del precio pleno y se cobran aparte al precio de caché.
      (COALESCE(e.input_tokens, 0) - COALESCE(e.cached_input_tokens, 0)) * p.input_usd / 1e6
    + COALESCE(e.cached_input_tokens, 0) * COALESCE(p.cached_input_usd, p.input_usd) / 1e6
    + COALESCE(e.output_tokens, 0) * p.output_usd / 1e6 AS usd
  FROM ai_usage_events e
  LEFT JOIN pricing p ON e.model LIKE p.model_prefix || '%'
)

-- Resumen por mes y fuente (chat / transcribe / agent:*).
SELECT
  to_char(month, 'YYYY-MM')                AS mes,
  source                                   AS fuente,
  model                                    AS modelo,
  COUNT(*)                                 AS llamadas,
  SUM(COALESCE(input_tokens, 0))           AS tokens_entrada,
  SUM(COALESCE(cached_input_tokens, 0))    AS tokens_cacheados,
  SUM(COALESCE(output_tokens, 0))          AS tokens_salida,
  ROUND(SUM(usd)::numeric, 4)              AS usd
FROM costed
GROUP BY month, source, model
ORDER BY month DESC, usd DESC;

-- Variantes útiles (descomenta la que necesites en lugar del SELECT de arriba):
--
-- Total del mes corriente en una sola cifra:
--   SELECT ROUND(SUM(usd)::numeric, 2) AS usd_mes_actual
--   FROM costed WHERE month = date_trunc('month', now());
--
-- Por empresa (para el futuro panel de super admin):
--   agrega e.company_id al SELECT/GROUP BY de `costed` y únelo a companies.
