# TP- TeknoDOCS

Aplicación modular para la gestión documental de proyectos SENA.

## Ejecución local

```powershell
py -m pip install -r requirements.txt
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
# Completa la contraseña en .streamlit/secrets.toml
py -m streamlit run app.py
```

La generación PDF utiliza Microsoft Word en Windows. En Linux utiliza
LibreOffice, declarado en `packages.txt` para Streamlit Community Cloud.

## Despliegue en Streamlit Community Cloud

1. Publica este repositorio en GitHub.
2. Crea una aplicación en Streamlit Community Cloud seleccionando `app.py`.
3. En **Advanced settings → Secrets**, configura:

```toml
[mysql]
host = "TU_HOST_MYSQL"
port = 3306
database = "TU_BASE_DE_DATOS"
user = "TU_USUARIO_MYSQL"
password = "TU_CONTRASEÑA_MYSQL"
```

4. Verifica que el servidor MySQL permita conexiones desde el despliegue.

`secrets.toml` y los PDF generados están excluidos del repositorio.

## Base de datos

La aplicación utiliza MySQL para proyectos, expertos y talentos. La conexión se
configura localmente en `.streamlit/secrets.toml`; este archivo está excluido de
Git y no debe compartirse ni incluirse en commits.

La creación de un proyecto, las personas nuevas y las relaciones de talento se
confirman en una única transacción. Los expertos y talentos existentes pueden
reutilizarse en proyectos posteriores.

Esta primera etapa incluye la gestión básica de proyectos, el proyecto activo,
la navegación por fases y el dashboard visual. Los módulos documentales se
incorporarán y validarán individualmente en etapas posteriores.
