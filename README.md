# 🔮 Sistema de Gestión de Consultantes & Astrología — Maru González

Sistema web desarrollado en Python con **Flask** para la captura de datos de consultantes, selección de servicios astrológicos/energéticos, gestión de archivos (Carta Natal y Revolución Solar) y panel administrativo con **alertas automatizadas de cumpleaños**.

---

## 🚀 Características Principales

* **Formulario Público de Registro:** 
  * Captura de datos personales y de contacto.
  * Captura de datos astrológicos exactos (Fecha, Hora y Lugar de nacimiento).
  * Selección múltiple de servicios (Astrología Evolutiva, Tarot, Magia Planetaria, Canalización, Radiestesia, etc.).
  * Campo de motivo/tema de consulta.
* **Panel de Administración (Admin Dashboard):**
  * Vista general de todos los consultantes registrados.
  * **Sistema de Alertas (30 días antes):** Notifica automáticamente qué clientes están a un mes o menos de cumplir años para agendar la **Revolución Solar**.
  * Ficha individual por cliente con sus servicios seleccionados.
  * **Gestión de Documentos:** Módulo para cargar y descargar archivos PDF/imágenes de la Carta Natal o Informes de Revolución Solar por año.

---

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python 3.x + Flask
* **Base de Datos:** SQLite3
* **Frontend:** HTML5 + Tailwind CSS (vía CDN)
* **Servidor en Producción:** Gunicorn

---

## 📁 Estructura del Proyecto

```text
Sistema/
│
├── app.py                     # Servidor principal y lógica de rutas
├── requirements.txt           # Dependencias de Python
├── database.db                # Base de datos SQLite (se genera automáticamente)
├── uploads/                   # Carpeta de almacenamiento para PDFs de Cartas
│
├── templates/                 # Plantillas HTML
│   ├── formulario.html        # Vista pública para el cliente
│   ├── exito.html             # Pantalla de confirmación de registro
│   ├── admin_dashboard.html   # Panel de control de Maru + Alertas
│   └── cliente_detalle.html   # Ficha individual del cliente + Subida de PDFs
│
└── static/                    # Archivos estáticos (CSS, JS, imágenes)