#!/bin/bash

# Definimos nombre del bucket y región del servidor
BUCKET_NAME="proyecto-datawave-dspt14"
REGION="us-central1"

# Verificamos si el bucket ya existe
if gsutil ls -b gs://$BUCKET_NAME/ 2>/de
v/null; then
  echo "🪣 El bucket gs://$BUCKET_NAME/ ya existe. Saltando creación..."
else
  # 1. Crear el bucket
  echo "🪣 Creando bucket: gs://${BUCKET_NAME}/..."
  gsutil mb -l $REGION gs://$BUCKET_NAME/
fi

# 2. Crear carpetas simuladas (subiendo archivos vacíos .keep)
echo "📁 Creando estructura lógica de carpetas..."
echo "" | gsutil cp - gs://$BUCKET_NAME/raw/reviews/.keep
echo "" | gsutil cp - gs://$BUCKET_NAME/raw/users/.keep
echo "" | gsutil cp - gs://$BUCKET_NAME/processed/.keep
echo "" | gsutil cp - gs://$BUCKET_NAME/logs/.keep

echo "✅ Listo. Estructura creada en GCS: gs://$BUCKET_NAME/"