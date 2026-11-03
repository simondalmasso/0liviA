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
- ≤13.5 GiB sostenidos por GPU;
- ≥20 tok/s objetivo, rechazo si <15;
- TTFT p50 ≤10 s a prompt 8K;
- contexto 32K estable;
- ≥6/10 fixtures sintéticos pass@1.

## Resultado

Al finalizar, descargar `/kaggle/working/metrics.json` y registrar su SHA-256 en el PR de resultados. No escribir resultados como PASS si la notebook no se ejecutó en GPU real.
