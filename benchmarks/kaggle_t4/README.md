# Kaggle T4×2 — laboratorio offline de 0liviA

Estado: **preparado; no ejecutado**. Este directorio contiene una plantilla reproducible para evaluación de modelos, no un servicio de inferencia.

## Límites obligatorios

- Notebook privado, ejecución manual y acotada.
- Sólo prompts sintéticos y fixtures artificiales; no subir chats, datos privados del repo, secretos, cookies ni credenciales.
- Pesos GGUF en un Kaggle Dataset privado adjunto como input. No incluir pesos en Git.
- No iniciar `llama-server`, vLLM, SGLang, HTTP, túneles, proxies, heartbeats ni conexiones con el Core/Actions.
- Comprobar la cuota real en el panel antes de activar GPU. La cuota publicada puede variar por demanda.
- Exportar sólo `metrics.json` saneado y detener manualmente la sesión.

La AUP vigente de Kaggle enumera *server farming* y actividad ajena a ML/data science entre los ejemplos de abuso de recursos. Los Terms limitan el uso a uso propio, interno, personal y no comercial. Ver fuentes en [docs/RESEARCH.md](../../docs/RESEARCH.md).

## Preparación del dataset privado

Adjuntar un dataset privado con:
- el archivo GGUF exacto;
- `manifest.json` al lado del GGUF.

Ejemplo de manifest (reemplazar los valores por los del artefacto real, no copiar un hash de ejemplo):

```json
{
  "model_id": "Qwen/Qwen3.6-35B-A3B",
  "source_url": "https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF",
  "license": "Apache-2.0 (confirmar en la ficha del artefacto)",
  "quantization": "UD-Q4_K_XL",
  "file": "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
  "sha256": "REEMPLAZAR_CON_SHA256_REAL",
  "notes": "Registrar la revisión exacta de la ficha y el tamaño del archivo"
}
```

El nombre del directorio de input de Kaggle no se asume; la notebook busca un único `manifest.json` bajo `/kaggle/input`. Si hay cero o más de uno, se detiene para evitar seleccionar el modelo equivocado.

## Notebook

Abrir `0livia_t4x2_offline_benchmark.ipynb` en Kaggle como notebook privado. Seleccionar GPU T4×2, confirmar cuota disponible y adjuntar el dataset privado. La compilación clona llama.cpp desde GitHub y fija el commit:

`2cbca389f515df455412dafa07e2b1359cc72a6d`

El notebook usa CUDA SM 7.5, `llama-bench` y `llama-cli`, con split multi-GPU por capas. No inicia ningún servidor.

## Secuencia de modelos

1. Qwen3.6-35B-A3B (primario).
2. Qwen3-Coder-30B-A3B-Instruct (coder comparador).
3. Qwen3.8-27B (comparador denso opcional).

Ejecutar un modelo por notebook/dataset para mantener los hashes y métricas inequívocos. Los puntajes del fabricante no sustituyen los resultados de esta prueba.

## Gates

Ver [docs/BENCHMARKS.md](../../docs/BENCHMARKS.md). Resumen:
- 2 T4 reales, SM 7.5;
- ≤13.5 GiB por GPU como objetivo, medidos durante la ejecución (muestreo cada 2 s; los picos transitorios más breves pueden no capturarse);
- ≥20 tok/s de decode como objetivo, rechazo si <15;
- throughput prefill registrado para prompts 512/2K/4K/8K;
- contexto 8K/16K/32K escalonado, con 32K como objetivo;
- ≥6/10 funciones sintéticas pass@1;
- código generado validado por AST y ejecutado en un subprocess con límites de CPU/memoria y timeout.

## Telemetría y límites de la prueba

La notebook separa `stdout` de `stderr`, captura muestras de VRAM de ambas T4 durante cada proceso e incluye el resultado de `llama-bench` dentro de `metrics.json`. El código generado se ejecuta en un subprocess aislado del kernel, con AST allowlist, 3 s de CPU, 512 MiB de memoria virtual y timeout padre de 10 s. Es defensa en profundidad para este fixture sintético, no un sandbox de propósito general. La plantilla no mide TTFT exacto ni un soak de 20 llamadas; ambos siguen siendo gates separados antes de promover un modelo. Tampoco evalúa cambios multiarchivo.

## Automatización controlada desde GitHub Actions

El repositorio incorpora dos workflows independientes:

1. [Kaggle API Preflight](../../.github/workflows/kaggle-api-preflight.yml): al integrar los cambios en `main`, instala la versión fijada del CLI, autentica usando el secret `OLIVIA_KAGGLE_API_TOKEN` y consulta `kaggle quota -v`. **No crea ni actualiza notebooks, no descarga pesos y no asigna GPU.**
2. [Kaggle T4×2 Offline Benchmark](../../.github/workflows/kaggle-t4x2-benchmark.yml): sólo se ejecuta manualmente desde Actions. Solicita el usuario de Kaggle, el slug `owner/dataset`, una duración entre 60 y 240 minutos, y dos confirmaciones separadas: que el dataset fue verificado como privado y que se autoriza consumir cuota GPU.

Antes de enviar el notebook, el workflow comprueba que:
- el secret esté disponible y la autenticación de Kaggle responda;
- la cuota GPU restante cubra la duración máxima solicitada;
- el dataset sea accesible y exponga exactamente un `manifest.json` y al menos un archivo GGUF.

La privacidad del dataset es una confirmación explícita del operador; el preflight no afirma verificarla automáticamente. El kernel creado se marca privado. El valor del token permanece en el entorno del runner de GitHub Actions y no se copia a `kernel-metadata.json`, al notebook ni a los datos de entrada de Kaggle.

**Importante:** `kaggle kernels push` inicia la ejecución y consume cuota. No se ejecuta en el preflight. El workflow T4×2 sólo se debe lanzar después de revisar la cuota y el contenido del dataset. El identificador `NvidiaTeslaT4` es el que Kaggle documenta para el pool T4×2; una hora de sesión T4×2 consume una hora de cuota GPU compartida.

Al finalizar, el workflow valida el archivo de métricas y publica únicamente un resumen allowlist en el resumen de GitHub Actions. No sube un artifact con el JSON crudo ni publica pesos, prompts, código generado, notas o rutas internas. Si el polling termina por timeout, inspeccionar el estado del kernel en Kaggle antes de reintentar para evitar una segunda ejecución accidental.

## Resultado

Al finalizar, descargar `/kaggle/working/metrics.json` y registrar su SHA-256 en el PR de resultados. No escribir resultados como PASS si la notebook no se ejecutó en GPU real.
