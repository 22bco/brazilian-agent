/**
 * leads_webapp.gs - Google Apps Script para recibir leads/handoffs del agente
 * y escribirlos en esta Google Sheet.
 *
 * CÓMO DESPLEGAR (una sola vez):
 *  1. Abre tu Google Sheet.
 *  2. Menú: Extensiones → Apps Script.
 *  3. Borra el contenido y pega TODO este archivo.
 *  4. Cambia SECRET abajo por una cadena tuya (la misma que pondrás en .env
 *     como LEADS_WEBAPP_SECRET).
 *  5. Implementar → Nueva implementación → Tipo: "Aplicación web".
 *       - Ejecutar como: Yo
 *       - Quién tiene acceso: "Cualquiera"
 *  6. Copia la URL que termina en /exec y ponla en .env como LEADS_WEBAPP_URL.
 *
 * Crea automáticamente dos pestañas: "Leads" y "Handoffs", con encabezados.
 */

const SECRET = "CAMBIA_ESTO_por_una_cadena_secreta";

const HEADERS = {
  Leads: ["timestamp", "id", "user_id", "nome", "contato", "interesse"],
  Handoffs: ["timestamp", "id", "user_id", "motivo", "resumo"],
};

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);

    if (body.secret !== SECRET) {
      return _json({ ok: false, error: "unauthorized" });
    }

    const type = body.type === "handoff" ? "Handoffs" : "Leads";
    const sheet = _sheet(type);
    const row = HEADERS[type].map((col) => body[col] !== undefined ? body[col] : "");
    sheet.appendRow(row);

    return _json({ ok: true, type: type, row: sheet.getLastRow() });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function doGet() {
  // Health check simple.
  return _json({ ok: true, service: "dyt-leads" });
}

function _sheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(HEADERS[name]);
    sheet.getRange(1, 1, 1, HEADERS[name].length).setFontWeight("bold");
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
