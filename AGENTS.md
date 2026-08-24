# Sistema modular de documentación de proyectos SENA

## Objetivo

Construir una nueva versión del software de generación documental tomando como referencia conceptual `smartgeeksws/softdocutecno_modular`, pero rediseñando la gestión de proyectos, la experiencia de usuario y todos los formatos institucionales.

El software anterior se utilizará únicamente como referencia. Los nuevos formatos deben analizarse nuevamente antes de desarrollar cada módulo.

## Principio principal

Todo documento debe pertenecer a un proyecto previamente creado.

Flujo:

**Crear proyecto → Guardar datos comunes → Abrir proyecto → Proyecto activo → Fase → Documento → Generar → Guardar estado**

La información común del proyecto no debe solicitarse repetidamente en cada documento.

## Proyecto activo

El sistema debe mantener un proyecto activo.

Los documentos deben recuperar automáticamente sus datos comunes.

La interfaz deberá mostrar permanentemente información que permita identificar el proyecto sobre el que se está trabajando.

## Pantalla inicial

Las opciones principales serán:

- Crear nuevo proyecto.
- Abrir proyecto existente.

La aplicación debe estar orientada a proyectos y no a documentos independientes.

## Experiencia de usuario

La navegación será:

**Proyecto → Fase → Documento**

La interfaz debe sentirse como un dashboard administrativo moderno.

## Interfaz

La estructura principal tendrá:

- Barra lateral izquierda persistente.
- Área principal de trabajo.
- Encabezado superior.
- Dashboard del proyecto.
- Tarjetas informativas.
- Formularios organizados por secciones.

## Menú lateral

Las fases documentales se mostrarán mediante botones desplegables tipo acordeón.

Ejemplo conceptual:

**Inicio / Dashboard**

**Proyectos**
- Crear proyecto
- Mis proyectos

**Fase de Inicio**
- Documentos correspondientes

**Fase de Ejecución**
- Documentos correspondientes

**Fase de Seguimiento**
- Documentos correspondientes

**Fase de Cierre**
- Documentos correspondientes

Los documentos y fases definitivos se establecerán después de analizar los nuevos formatos.

## Identidad visual institucional

Paleta:

- Verde principal: `#39A900`
- Verde oscuro: `#007832`
- Azul oscuro: `#00304D`
- Morado: `#71277A`
- Cian: `#50E5F9`
- Amarillo: `#FDC300`

El verde `#39A900` será el color principal de acciones, selección y elementos institucionales.

Blanco y grises claros serán utilizados para fondos, formularios y tarjetas.

## Dashboard

Al abrir un proyecto se mostrará su estado documental.

Podrá presentar:

- Información general.
- Documentos generados.
- Documentos pendientes.
- Porcentaje de avance.
- Estado de cada fase.
- Accesos rápidos.

## Estados documentales

Los documentos podrán manejar estados como:

- Pendiente.
- Borrador.
- Generado.

## Formularios

Los formularios deberán dividirse conceptualmente en:

1. Identificación del documento.
2. Información del proyecto.
3. Información específica.
4. Contenido técnico.
5. Acciones.

Los datos existentes del proyecto deberán precargarse automáticamente.

## Nuevos formatos

Todos los formatos institucionales cambiaron.

Por tanto:

- No reutilizar automáticamente formularios anteriores.
- No asumir campos de la versión anterior.
- Analizar cada plantilla nueva.
- Separar datos comunes y específicos.
- Validar visualmente cada documento generado.

## Metodología de desarrollo

Cada módulo seguirá:

**Entender → Diseñar → Construir → Probar → Validar → Continuar**

No desarrollar todos los documentos simultáneamente.

## Proyecto anterior

Referencia:

`https://github.com/smartgeeksws/softdocutecno_modular`

El repositorio anterior no debe modificarse.

Puede reutilizarse como referencia para patrones técnicos que continúen siendo útiles.

## Arquitectura

La aplicación conservará un enfoque modular separando conceptualmente:

- Aplicación principal.
- Configuración.
- Interfaz.
- Gestión de proyectos.
- Servicios.
- Utilidades.
- Módulos documentales.
- Plantillas.
- Recursos.
- Datos.
- Archivos generados.

## Reglas de modificación

- No modificar archivos fuera del alcance solicitado.
- No alterar módulos validados innecesariamente.
- Centralizar los datos comunes del proyecto.
- Evitar lógica duplicada.
- Centralizar estilos visuales.
- No inventar requisitos.
- Mantener el proyecto funcional después de cada cambio.
- Validar cada módulo antes de continuar.

## Git

Los cambios deben ser pequeños y verificables.

Cada funcionalidad validada deberá almacenarse mediante commits descriptivos.

No mezclar cambios de diferentes módulos sin necesidad.

## Instrucciones para Codex

Antes de modificar código:

1. Leer este archivo.
2. Respetar las decisiones funcionales y visuales.
3. No inventar requisitos.
4. No realizar migraciones masivas del sistema anterior.
5. Limitar modificaciones al alcance solicitado.
6. Conservar módulos ya aprobados.
7. Utilizar código modular y mantenible.
8. Esperar instrucciones cuando falten datos de los formatos institucionales.

## Estado actual

Actualmente están definidos:

- Sistema basado en proyectos.
- Creación y apertura de proyectos.
- Proyecto activo.
- Reutilización de información común.
- Dashboard.
- Menú lateral desplegable.
- Identidad visual SENA.
- Desarrollo módulo por módulo.
- Revisión completa de los nuevos formatos.

Todavía no están definidos:

- Campos definitivos del proyecto.
- Fases definitivas.
- Documentos definitivos.
- Plantillas nuevas.
- Reglas específicas de cada módulo.
- Modelo definitivo de almacenamiento.