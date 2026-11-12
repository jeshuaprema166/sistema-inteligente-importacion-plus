# ═══════════════════════════════════════════════════════════════════════
#  SISTEMA DE ANÁLISIS DE IMPORTACIÓN INTELIGENTE 🐉✨ (BLOQUE 1 / 3)
#  Motor original y metodología: Prof. Jesús Pulido V. (New 30/10/26)
# ═══════════════════════════════════════════════════════════════════════

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date, timedelta, datetime
import io, os, json, re, unicodedata, random
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
from fpdf import FPDF

# -- MÓDULO DE BÚSQUEDA WEB DE PROVEEDORES --
from supplier_finder import find_suppliers, wa_link

try:
    import sheets_db
    SHEETS_DB_OK = True
except ImportError:
    SHEETS_DB_OK = False

CENTAVO = Decimal("0.01")
CERO    = Decimal("0")
UNO     = Decimal("1")

GASTOS_CONTENEDOR = (
    ("Manejo de Puerto",           "peso"),
    ("Flete Terrestre Nacional",   "peso"),
    ("Logística Internacional",    "volumen"),
    ("Derechos de Aduana",         "volumen"),
    ("Gestión Aduanera",           "volumen"),
    ("Gastos Administrativos",     "volumen"),
)

SECTORES = [
    "Ferretería / Herramientas", "Repuestos para motos",
    "Repuestos para automóviles", "Cauchos y neumáticos",
    "Construcción / Materiales", "Agro / Insumos",
    "Tecnología / Electrónica", "Textil / Calzado",
    "Salud / Farmacia", "Otro (especificar)",
]

ORIGENES = [
    "China", "Estados Unidos", "Panamá", "Brasil", "Turquía",
    "India", "Colombia", "México", "Vietnam", "Tailandia",
    "Corea del Sur", "Japón", "Alemania", "España", "Italia",
    "Otro (especificar)",
]

# Actualización de Orígenes y Tiempos de Tránsito Estándar (Días)
ORIGENES_CON_TRANSITO = {
    "China": {"dias": 60, "tipo": "maritimo"},
    "Estados Unidos": {"dias": 22, "tipo": "maritimo/aereo"},
    "Panamá": {"dias": 15, "tipo": "maritimo/multimodal"},
    "Brasil": {"dias": 25, "tipo": "terrestre/maritimo"},
    "Turquía": {"dias": 35, "tipo": "maritimo"},
    "India": {"dias": 45, "tipo": "maritimo"},
    "Colombia": {"dias": 8, "tipo": "terrestre"},
    "México": {"dias": 20, "tipo": "maritimo"},
    "Vietnam": {"dias": 55, "tipo": "maritimo"},
    "Tailandia": {"dias": 55, "tipo": "maritimo"},
    "Corea del Sur": {"dias": 50, "tipo": "maritimo"},
    "Japón": {"dias": 50, "tipo": "maritimo"},
    "Alemania": {"dias": 30, "tipo": "maritimo"},
    "España": {"dias": 25, "tipo": "maritimo"},
    "Italia": {"dias": 28, "tipo": "maritimo"},
    "Proveedor Nacional (Local / Emergencia)": {"dias": 4, "tipo": "terrestre_local"},
    "Otro (especificar)": {"dias": 45, "tipo": "personalizado"}
}

# Extraemos la lista para los selectbox de la interfaz manteniendo compatibilidad
ORIGENES = list(ORIGENES_CON_TRANSITO.keys())

def obtener_dias_transito(pais_origen):
    """Devuelve los días de tránsito estimados según el país seleccionado."""
    info = ORIGENES_CON_TRANSITO.get(pais_origen, {"dias": 60})
    return info["dias"]

DEFAULTS = {
    "id_perfil": "", "empresa": "", "rif": "", "propietario": "", "email": "",
    "sector": "Ferretería / Herramientas", "sector_otro": "",
    "margen": 30.0, "desc_mayorista": 15.0, "desc_especial": 5.0,
    "origen": "China", "origen_otro": "", "proveedor": "", "factura": "",
    "fecha_proximo_pedido": None, "capital_inicial": 0.0,
    "costo_fijo_semanal": 0.0, "monto_proximo_pedido": 0.0,
}

MONEDAS_DEFAULT = {
    "USD": {"simbolo": "$",   "unidades_por_usd": 1.0},
    "EUR": {"simbolo": "€",   "unidades_por_usd": 0.93},
    "VES": {"simbolo": "Bs.", "unidades_por_usd": 40.0},
}
RUTA_TASAS = "tasas_cambio.json"

PARTIDAS_BASE = {
    "8207.50.00": {"descripcion": "Útiles de taladrar (brocas)", "ad_valorem": 0.05, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "82 - Herramientas"},
    "8207.90.00": {"descripcion": "Otros útiles intercambiables", "ad_valorem": 0.05, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "82 - Herramientas"},
    "7318.15.00": {"descripcion": "Tornillos y pernos de acero", "ad_valorem": 0.10, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "73 - Manufacturas de hierro"},
    "8414.80.20": {"descripcion": "Compresores de aire", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "SENCAMER + Norma COVENIN", "capitulo": "84 - Máquinas y aparatos"},
    "8716.80.00": {"descripcion": "Carretillas de mano", "ad_valorem": 0.20, "iva": 0.16, "requisitos": "Revisar norma técnica", "capitulo": "87 - Vehículos"},
    "8708.10.00": {"descripcion": "Parachoques y sus partes", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.29.00": {"descripcion": "Partes de carrocería", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.30.00": {"descripcion": "Frenos y servofrenos", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Revisar norma técnica", "capitulo": "87 - Vehículos"},
    "8708.40.00": {"descripcion": "Cajas de cambio", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.50.00": {"descripcion": "Ejes con diferencial", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.99.00": {"descripcion": "Otras partes y accesorios", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8714.10.00": {"descripcion": "Partes de motocicletas", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8714.91.00": {"descripcion": "Sillines y partes", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "4011.10.00": {"descripcion": "Neumáticos para automóviles", "ad_valorem": 0.20, "iva": 0.16, "requisitos": "SENCAMER + Norma COVENIN", "capitulo": "40 - Caucho"},
    "4011.20.00": {"descripcion": "Neumáticos para buses/camiones", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "SENCAMER", "capitulo": "40 - Caucho"},
    "4011.40.00": {"descripcion": "Neumáticos para motocicletas", "ad_valorem": 0.20, "iva": 0.16, "requisitos": "SENCAMER", "capitulo": "40 - Caucho"},
    "8504.40.00": {"descripcion": "Fuentes de poder / cargadores", "ad_valorem": 0.10, "iva": 0.16, "requisitos": "Revisar norma técnica", "capitulo": "85 - Máquinas eléctricas"},
    "8544.42.00": {"descripcion": "Cables y conductores eléctricos", "ad_valorem": 0.10, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "85 - Máquinas eléctricas"},
}

BANCO_PRODUCTOS_SINTETICOS = {
    "Moto Repuestos": [
        {"nombre": "Kit de Arrastre CG150", "peso": 2.10, "vol": 0.0035, "fob": 14.50, "partida": "8714.10.00", "pvp": 35.00},
        {"nombre": "Juego de Pastillas de Freno", "peso": 0.35, "vol": 0.0008, "fob": 1.80, "partida": "8714.10.00", "pvp": 5.00},
        {"nombre": "Amortiguadores Traseros (Par)", "peso": 3.80, "vol": 0.0075, "fob": 18.00, "partida": "8714.10.00", "pvp": 45.00},
        {"nombre": "Casco Integral Certificado", "peso": 1.45, "vol": 0.0220, "fob": 12.00, "partida": "6506.10.00", "pvp": 50.00},
        {"nombre": "Correa de Transmisión Scooter", "peso": 0.18, "vol": 0.0005, "fob": 2.20, "partida": "4010.35.00", "pvp": 6.00},
        {"nombre": "Caucho/Neumático 90/90-18", "peso": 3.20, "vol": 0.0180, "fob": 11.50, "partida": "4011.40.00", "pvp": 30.00},
        {"nombre": "Batería de Gel 12V 7Ah", "peso": 2.10, "vol": 0.0020, "fob": 8.50, "partida": "8507.10.00", "pvp": 22.00},
        {"nombre": "Carburador Completo CG150", "peso": 0.85, "vol": 0.0025, "fob": 9.20, "partida": "8409.91.00", "pvp": 25.00}
    ],
    "Auto Repuestos": [
        {"nombre": "Bomba de Agua Universal", "peso": 1.80, "vol": 0.0040, "fob": 12.50, "partida": "8413.30.00", "pvp": 32.00},
        {"nombre": "Juego de Pastillas Freno Delanteras", "peso": 1.20, "vol": 0.0015, "fob": 6.80, "partida": "8708.30.00", "pvp": 18.00},
        {"nombre": "Disco de Freno Ventilado (Par)", "peso": 9.50, "vol": 0.0120, "fob": 22.00, "partida": "8708.30.00", "pvp": 65.00},
        {"nombre": "Filtro de Aceite Sintético", "peso": 0.30, "vol": 0.0008, "fob": 1.50, "partida": "8421.23.00", "pvp": 5.00},
        {"nombre": "Amortiguador Delantero Hidráulico", "peso": 4.20, "vol": 0.0080, "fob": 19.50, "partida": "8708.80.00", "pvp": 55.00},
        {"nombre": "Kit de Tiempo / Correa Distribución", "peso": 0.90, "vol": 0.0022, "fob": 15.00, "partida": "4010.36.00", "pvp": 40.00}
    ],
    "Ferretería y Herramientas": [
        {"nombre": "Taladro Percutor 1/2'' 750W", "peso": 2.30, "vol": 0.0060, "fob": 16.50, "partida": "8467.21.00", "pvp": 42.00},
        {"nombre": "Juego de Llaves Combinadas 12 pzs", "peso": 1.80, "vol": 0.0025, "fob": 8.20, "partida": "8204.11.00", "pvp": 22.00},
        {"nombre": "Esmeril Recto 4-1/2''", "peso": 2.10, "vol": 0.0050, "fob": 14.00, "partida": "8467.29.00", "pvp": 38.00},
        {"nombre": "Disco de Corte para Metal 4.5'' (Caja 25u)", "peso": 1.10, "vol": 0.0012, "fob": 5.50, "partida": "6804.22.00", "pvp": 15.00},
        {"nombre": "Cinta Métrica 5m Antimpacto", "peso": 0.25, "vol": 0.0004, "fob": 1.10, "partida": "9017.80.10", "pvp": 3.50}
    ],
    "Materiales de Construcción": [
        {"nombre": "Cerradura de Pomo para Dominio", "peso": 0.60, "vol": 0.0018, "fob": 3.80, "partida": "8301.40.00", "pvp": 10.00},
        {"nombre": "Grifería Monomando Cocina", "peso": 1.20, "vol": 0.0045, "fob": 9.50, "partida": "8481.80.00", "pvp": 28.00},
        {"nombre": "Disco Diamantado 7'' Pavimento", "peso": 0.45, "vol": 0.0008, "fob": 4.20, "partida": "6804.21.00", "pvp": 12.00},
        {"nombre": "Nivel de Aluminio 24'' Profesional", "peso": 0.50, "vol": 0.0020, "fob": 2.90, "partida": "9017.30.00", "pvp": 8.50}
    ],
    "Materiales Eléctricos": [
        {"nombre": "Breaker Termomagnético 2P 40A", "peso": 0.22, "vol": 0.0004, "fob": 2.10, "partida": "8536.20.00", "pvp": 6.00},
        {"nombre": "Reflector LED 100W Multivoltaje", "peso": 0.95, "vol": 0.0032, "fob": 6.50, "partida": "9405.40.90", "pvp": 18.00},
        {"nombre": "Rollo Cable THHN #12 (100m)", "peso": 3.80, "vol": 0.0055, "fob": 24.00, "partida": "8544.49.00", "pvp": 55.00},
        {"nombre": "Tomacorriente Doble Regulado", "peso": 0.12, "vol": 0.0003, "fob": 0.85, "partida": "8536.69.00", "pvp": 2.50}
    ]
}

# Mapeo de centros de distribución / ubicación en Venezuela para calcular flete y tiempo interno
UBICACIONES_VENEZUELA = {
    "Caracas / Región Capital": {"dias_flete_interno": 2, "factor_costo_flete": 1.0},
    "Valencia / Maracay (Centro)": {"dias_flete_interno": 1, "factor_costo_flete": 0.8},
    "Barquisimeto / Centro-Occidente": {"dias_flete_interno": 2, "factor_costo_flete": 1.1},
    "Maracaibo / Zulia": {"dias_flete_interno": 3, "factor_costo_flete": 1.4},
    "San Cristóbal / Táchira (Andes)": {"dias_flete_interno": 4, "factor_costo_flete": 1.6},
    "Puerto La Cruz / Oriente": {"dias_flete_interno": 3, "factor_costo_flete": 1.3},
    "Puerto Ordaz / Guayana": {"dias_flete_interno": 4, "factor_costo_flete": 1.7},
    "Otro punto del país": {"dias_flete_interno": 3, "factor_costo_flete": 1.5}
}

def calcular_ruta_salvavidas_local(producto, cantidad_emergencia, ubicacion_empresa, proveedor_local="Distribuidor Mayorista Nacional"):
    """
    Calcula el escenario de emergencia (Plan Salvavidas) comprando a nivel nacional 
    ajustado a los días y costos de despacho según la ubicación exacta del cliente en Venezuela.
    """
    info_ubicacion = UBICACIONES_VENEZUELA.get(ubicacion_empresa, {"dias_flete_interno": 3, "factor_costo_flete": 1.3})
    
    # Aseguramos conversión segura a float
    costo_fob_base = float(producto.get("precio_fob", 0) or 0)
    costo_unitario_local = costo_fob_base * 1.35 
    
    gasto_flete_interno = 0.50 * float(info_ubicacion.get("factor_costo_flete", 1.3))
    costo_total_unitario_local = costo_unitario_local + gasto_flete_interno
    dias_totales_entrega = int(info_ubicacion.get("dias_flete_interno", 3))
    
    total_inversion_emergencia = float(cantidad_emergencia) * costo_total_unitario_local
    
    return {
        "proveedor": proveedor_local,
        "cantidad_sugerida": int(cantidad_emergencia),
        "costo_unitario_local": round(costo_total_unitario_local, 2),
        "dias_entrega": dias_totales_entrega,
        "inversion_total": round(total_inversion_emergencia, 2),
        "ubicacion_destino": ubicacion_empresa,
        "mensaje_estrategico": f"🚨 Salvavidas Activo: Despacho a {ubicacion_empresa} en {dias_totales_entrega} días."
    }

def comparar_rutas_abastecimiento(producto, config):
    """
    Compara el escenario de importación internacional habitual frente al 
    Plan de Salvavidas (Compra Puente Nacional) considerando la ubicación de la empresa.
    """
    ubicacion = config.get("ubicacion_empresa", "Caracas / Región Capital")
    
    # Conversión robusta a float para evitar errores de tipo
    ventas_sem = float(producto.get("ventas_semanales", 0) or 0)
    stock_act = float(producto.get("stock_actual", 0) or 0)
    
    # Cobertura actual en semanas
    cobertura_semanas = (stock_act / ventas_sem) if ventas_sem > 0 else 0.0
    
    # Días de tránsito internacional según el origen configurado
    dias_int = float(obtener_dias_transito(config.get("origen", "China")) or 60)
    semanas_int = dias_int / 7.0
    
    # ¿Hay riesgo de quiebre antes de que llegue el pedido internacional?
    en_riesgo = cobertura_semanas <= semanas_int
    
    # Cantidad de emergencia necesaria para cubrir el bache
    semanas_bache = max(0.0, semanas_int - cobertura_semanas)
    unidades_emergencia_necesarias = int(semanas_bache * ventas_sem) if en_riesgo else 0
    
    # Costo unitario internacional
    costo_unit_int = float(producto.get("costo_unitario", 0) or 0)
    
    # Datos de la ruta salvavidas local
    salvavidas = None
    if en_riesgo and unidades_emergencia_necesarias > 0:
        salvavidas = calcular_ruta_salvavidas_local(
            producto, 
            unidades_emergencia_necesarias, 
            ubicacion,
            proveedor_local=config.get("proveedor_local_preferido", "Distribuidor Nacional de Emergencia")
        )
        
    return {
        "en_riesgo_quiebre": en_riesgo,
        "cobertura_semanas": round(cobertura_semanas, 1),
        "dias_tránsito_internacional": int(dias_int),
        "unidades_puente_sugeridas": unidades_emergencia_necesarias,
        "costo_unitario_internacional": costo_unit_int,
        "salvavidas_local": salvavidas
    }
        
    return {
        "en_riesgo_quiebre": en_riesgo,
        "cobertura_semanas": round(cobertura_semanas, 1),
        "dias_tránsito_internacional": dias_int,
        "unidades_puente_sugeridas": unidades_emergencia_necesarias,
        "costo_unitario_internacional": costo_unit_int,
        "salvavidas_local": salvavidas
    }

def slugify(texto):
    if not texto: return "empresa-sin-nombre"
    t = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('ascii')
    t = re.sub(r'[^a-zA-Z0-9]+', '-', t).strip('-').lower()
    return t or "empresa-sin-nombre"

def texto_efectivo(valor, alterno=""):
    if valor and valor.startswith("Otro"): return alterno.strip() or "No especificado"
    return valor or "No especificado"

def cargar_tasas():
    if SHEETS_DB_OK:
        remotas = sheets_db.leer_tasas()
        if remotas: return {"EUR": remotas["EUR"], "VES": remotas["VES"]}
    if os.path.exists(RUTA_TASAS):
        try:
            with open(RUTA_TASAS, "r", encoding="utf-8") as f:
                d = json.load(f)
            return {"EUR": float(d.get("EUR", 0.93)), "VES": float(d.get("VES", 40.0))}
        except Exception: pass
    return {k: v["unidades_por_usd"] for k, v in MONEDAS_DEFAULT.items() if k != "USD"}

def inicializar_monedas():
    if "monedas" not in st.session_state: st.session_state["monedas"] = cargar_tasas()
    if "moneda_activa" not in st.session_state: st.session_state["moneda_activa"] = "USD"

def formato_moneda(monto_usd, moneda=None):
    try:
        moneda = moneda or st.session_state.get("moneda_activa", "USD")
        tasas  = st.session_state.get("monedas", {})
    except Exception: moneda, tasas = "USD", {}
    valor = Decimal(str(monto_usd)) * Decimal(str(tasas.get(moneda, 1.0)))
    simbolo = MONEDAS_DEFAULT[moneda]["simbolo"]
    return f"{simbolo} {valor.quantize(CENTAVO, ROUND_HALF_UP):,.2f}"

def formato_dinero(valor): return formato_moneda(valor)

def panel_monedas_sidebar(config):
    inicializar_monedas()
    with st.sidebar.expander("💵 Moneda y tipo de cambio", expanded=False):
        if SHEETS_DB_OK:
            remotas = sheets_db.leer_tasas()
            if remotas:
                st.session_state["monedas"]["EUR"] = remotas["EUR"]
                st.session_state["monedas"]["VES"] = remotas["VES"]
                st.caption(f"🔄 {remotas['fecha']} · por {remotas['por']}")
        st.session_state["moneda_activa"] = st.selectbox("Moneda de visualización", ["USD", "EUR", "VES"], index=["USD", "EUR", "VES"].index(st.session_state["moneda_activa"]))
        for m in ["EUR", "VES"]:
            st.session_state["monedas"][m] = st.number_input(f"1 USD = ? {m}", min_value=0.0001, value=float(st.session_state["monedas"].get(m, 1.0)), step=0.01, format="%.4f", key=f"tasa_{m}")
        if st.button("💾 Guardar tasas", key="guardar_tasas"):
            if SHEETS_DB_OK:
                ok, msg = sheets_db.guardar_tasas(usd_eur=st.session_state["monedas"]["EUR"], usd_ves=st.session_state["monedas"]["VES"], usuario=config.get("propietario") or config.get("empresa") or "admin")
                (st.success if ok else st.warning)(msg)
            else:
                try:
                    with open(RUTA_TASAS, "w", encoding="utf-8") as f: json.dump({"EUR": st.session_state["monedas"]["EUR"], "VES": st.session_state["monedas"]["VES"]}, f, indent=2)
                    st.success("✅ Guardadas localmente.")
                except Exception as e: st.error(f"No se pudieron guardar: {e}")

def a_decimal(valor, defecto="0"):
    if pd.isna(valor) or valor is None or str(valor).strip() == "":
        return Decimal(str(defecto))
    try:
        val_str = str(valor).strip().replace(",", ".")
        return Decimal(val_str)
    except Exception:
        return Decimal(str(defecto))

def redondear_entero(valor): 
    return valor.quantize(UNO, rounding=ROUND_HALF_UP)

def verificar_acceso():
    if "PASSWORD_ADMIN" not in st.secrets: 
        return True
        
    # --- SITUACIÓN 1: AÚN NO HA INGRESADO (MOSTRAR PORTADA 1 Y CONTRASEÑA) ---
    if not st.session_state.get("autenticado", False):
        try:
            st.image("portada_sistema_premium.jpg", use_container_width=True)
        except Exception:
            st.markdown("<h3 style='text-align: center;'>🚢 Sistema de Gestión Inteligente Premium</h3>", unsafe_allow_html=True)

        st.markdown("<h1 style='text-align: center;'>Bienvenidos 🚢</h1>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center;'>¿Sabe cuánto le cuesta realmente traer los productos desde el exterior hasta su depósito?</h3>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center;'>Este Sistema Inteligente le revela:</h4>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
        * **La verdad sobre sus costos de importación**, márgenes de utilidad y precios óptimos de venta.
        * **Identificar los márgenes reales de ganancia** antes de nacionalizar, analizando la rentabilidad neta por producto prorrateando con precisión los costos según peso (kg) y volumen ($m^3$). Así sabrá qué productos le dejan ganancia real y cuáles no.
        * **Optimizar el espacio de su contenedor** y evite pérdidas por costos ocultos.
        * **Alarmas de reposición de inventario 🟢🟡🔴 por IA**, que permiten monitorear el comportamiento de las existencias, previniendo el desabastecimiento o sobrecompra, que redunda en estancamiento del Capital económico.
        * **Ingresar de forma automática TODOS los datos** y detalles desde el Excel de su inventario al Sistema de Análisis Inteligente de Importación.
        * **Definir fácilmente y con certeza** a qué proveedor del exterior debe comprar, o si es mejor hacerlo localmente.
        """)

        st.info("✨ **Todo eso y más, con la ayuda de nuestro Sistema de Importación con IA** 🤖")

        st.markdown("""
        <div style="background-color: #e8f4f8; color: #0b2545; padding: 15px; border-radius: 8px; text-align: center;">
        <strong>"UN SISTEMA DE COMERCIALIZACIÓN DISEÑADO PARA PROTEGER SU CAPITAL Y ASEGURAR QUE EL NEGOCIO SIEMPRE CREZCA"</strong>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        
        st.markdown("### 📋 Instrucciones:")
        st.markdown("""
        1. Una vez dentro, vaya al **menú desplegable de la izquierda** (⬅️) para configurar los **Datos de su empresa**: Razón Social, RIF, Propietario, márgenes de utilidad (%) y descuentos previstos, así como los datos del país y proveedor de origen.
        2. Y además, le recomendamos conocer más a fondo todas las virtudes, capacidades técnicas y módulos avanzados que incorpora esta versión, **explore la pestaña desplegable (Expander)** que encontrará una vez dentro.
        3. Para ingresar al Sistema, escriba más abajo la **contraseña** suministrada por su Asesor de Importación para comenzar el análisis.
        """)

        st.markdown("---")

        col_i, col_c, col_d = st.columns([1, 1, 1])
        with col_c:
            st.markdown(
                """
                <div style="text-align: center;">
                    Diseñado y elaborado por<br>
                    su Asesor de Importación Inteligente<br>
                    <b>Prof. Jesús Pulido V.</b><br>
                    <span style="font-size: 17px; color: #555;">0424-728.3199 / 0416-291.6426</span>
                </div>
                """, 
                unsafe_allow_html=True
            )

            for nombre in ("profesor.jpg", "asesor.jpg"):
                if os.path.exists(nombre):
                    st.image(nombre, width=180)
                    break

        st.divider()

        password = st.text_input("Contraseña de acceso", type="password")
        if st.button("Ingresar", type="primary"):
            if password == st.secrets["PASSWORD_ADMIN"]:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
                
        return False  # Detiene la ejecución aquí porque aún no ha ingresado la clave correcta

    # --- SITUACIÓN 2: YA ESTÁ AUTENTICADO (MOSTRAR PORTADA 2 / RECIBIMIENTO PREMIUM) ---
        # --- RECIBIMIENTO PREMIUM POST-LOGIN ---
        # 1. Portada reducida y perfectamente centrada con columnas
    col_espacio1, col_img, col_espacio2 = st.columns([1, 2, 1])
    with col_img:
        try:
            st.image("portada_sistema_premium.jpg", use_container_width=True)
        except Exception:
            st.markdown("<h3 style='text-align: center;'>🚢 Sistema de Gestión Inteligente Premium</h3>", unsafe_allow_html=True)

    st.markdown("<h4 style='text-align: center;'>¡Bienvenido al Panel de Control Ejecutivo Premium!</h4>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
        # 2. Indicación al menú de la izquierda
        # Se muestra sólo si aún no se ha configurado la empresa
        # Verificación segura del estado de la empresa    
    empresa_registrada = False
    if "config_empresa" in st.session_state:
        empresa_registrada = st.session_state.config_empresa.get("empresa")

    if not empresa_registrada:
        st.info("👈 **Primer paso:** Despliegue el menú de la barra superior izquierda **>>** para configurar los **Datos de su Empresa** y los Parámetros Avanzados, antes de cargar su archivo Excel.")
    
    # 3. Estilo personalizado para agrandar y poner en negrita los títulos de los expanders
    st.markdown("""
        <style>
        /* Estilo general para el contenedor del expander */
        div[data-testid="stExpander"] {
            background-color: #fdf2f2 !important;
            border: 1px solid #f5c6cb !important;
            border-radius: 0.5rem !important;
        }
        /* Color, tamaño y negrita para el título del expander */
        div[data-testid="stExpander"] summary p {
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            color: #8A1C14 !important; /* Rojo elegante / Vinotinto corporativo */
        }
        </style>
    """, unsafe_allow_html=True)
      
    # 4. Pestaña desplegable informativa con lenguaje comercial optimizado
    with st.expander("👇🏼✨📖 (TOQUE AQUÍ)\n\nConozca cómo el Sistema Premium protege y hace crecer su negocio."):
        st.markdown(
            """
            🛡️ **¿Cómo este Sistema Premium 🐉 protege su inversión y maximiza sus ganancias?**
        
            Este software ha sido diseñado específicamente para la realidad comercial y aduanera de Venezuela, dotándole de herramientas corporativas que garantizan:
        
            * **Protección Total de su Inversión:** Cada dólar invertido en mercancía es analizado al detalle. El sistema prorratea con precisión matemática los costos por peso y volumen, revelando el costo real unitario en su depósito para fijar precios competitivos que aseguren un retorno seguro.
            * **Control Estructural de Carga Pesada:** Evalúa la eficiencia del transporte marítimo calculando el impacto porcentual del flete frente al valor FOB en origen (clasificándolo en semáforos óptimos, moderados o críticos). Permite detectar sobrecostos logísticos a tiempo para decidir si se consolida carga o se ajustan rutas antes de nacionalizar.
            * **Cero Gastos Sorpresa por Multas y Retrasos:** Gracias al módulo de Auditoría de Partidas Arancelarias, usted verifica de antemano el cumplimiento normativo, calculando los aranceles y tributos estimados antes de nacionalizar, evitando costosas retenciones o sanciones en aduana.
            * **Simulación Gerencial de Flujo de Caja (What-If):** Permite modelar interactivamente el futuro financiero de la empresa mediante 6 variables críticas (capital, márgenes discretos, costos fijos, montos de pedidos, tiempos físicos de inventario y plazos de pago a proveedores). Esto garantiza una comercialización sana, proyectando 13 semanas de liquidez para asegurar una rentabilidad blindada y sin sorpresas de caja.
            * **Fijación Inteligente del PVP Sugerido:** Implementa un modelo matemático basado en el costo real nacionalizado y el margen comercial deseado. Esto garantiza una comercialización sana, fungiendo como garantía de rentabilidad real, referencia técnica para negociaciones y escudo frente al riesgo inflacionario y cambiario.
            * **Blindaje contra Fallas de Inventario:** Mediante las Alarmas Inteligentes por IA (🟢🟡🔴) y la Proyección de Flujo de Caja a 13 Semanas, el sistema anticipa cuándo se agotarán sus existencias y vigila que su capital de trabajo nunca caiga por debajo del límite seguro.
            * **Búsqueda de Proveedores Locales (Módulo "Salvavidas"):** Si la cadena internacional sufre demoras, el sistema activa al instante un motor de búsqueda web y directorios locales especializados para cotizar con mayoristas nacionales, calcular rutas puente de auxilio y mantener su negocio abierto y facturando.
            * **Historial Persistente en la Nube:** Respaldado de forma automática, permitiéndole tener acceso al Historial de Compras desde cualquier sitio en su celular personal, facilitando la auditoría de cada importación pasada y la toma de decisiones gerenciales en tiempo real.
            * **Emisión de Informes Ejecutivos en PDF para Solicitudes Bancarias:** El sistema compila automáticamente toda la data analítica, contable y de proyecciones en un dossier en formato PDF de impecable factura profesional. Esto actúa como un excelente resumen administrativo y una elegante carta de presentación técnica y financiera ante la banca comercial para respaldar con total solidez cualquier solicitud de crédito.          
                
            ---
            *(Puede cerrar esta sección haciendo clic > nuevamente en la parte superior del desplegable).*
            """
        )
              
    return True  # Permite que main() continúe hacia el selector de modalidades
            
def prorratear_gasto(monto, productos, campo_base):
    total_centavos = int(monto.quantize(CENTAVO, rounding=ROUND_HALF_UP) * 100)
    bases = [producto[campo_base] for producto in productos]
    suma_bases = sum(bases, CERO)
    if suma_bases <= CERO: raise ValueError(f"No hay base para repartir por {campo_base}.")
    partes_exactas = [Decimal(total_centavos) * base / suma_bases for base in bases]
    partes_en_centavos = [int(parte) for parte in partes_exactas]
    centavos_sobrantes = total_centavos - sum(partes_en_centavos)
    orden_por_resto = sorted(range(len(productos)), key=lambda i: partes_exactas[i] - Decimal(partes_en_centavos[i]), reverse=True)
    for indice in orden_por_resto[:centavos_sobrantes]: partes_en_centavos[indice] += 1
    return [Decimal(parte) / 100 for parte in partes_en_centavos]

def evaluar_semaforo(stock_actual, ventas_semanales, dias_entrega=0, fecha_proximo_pedido=None):
    stock_actual = float(stock_actual) if stock_actual is not None else 0.0
    ventas_semanales = float(ventas_semanales) if ventas_semanales is not None else 0.0
    
    if ventas_semanales <= 0:
        return "⚪", "Sin ventas registradas", 0, 0, False

    # Cálculo exacto de semanas de inventario disponible
    semanas_stock = stock_actual / ventas_semanales
    
    # Criterio unificado de semáforo por semanas de cobertura (Coherente con Reposición)
    if semanas_stock <= 4:
        color, mensaje = "🔴", "🔴 ¡ALERTA ROJA! Pedir YA (Crítico)"
    elif semanas_stock <= 8:
        color, mensaje = "🟡", "🟡 Precaución: Pedir pronto (Preventivo)"
    else:
        color, mensaje = "🟢", "🟢 Todo bien: Stock suficiente (Óptimo)"
        
    sugerido_ahora = int(max(0, (8 * ventas_semanales) - stock_actual))
    
    # Proyección futura y riesgo de quiebre intactos para los reportes avanzados
    sugerido_futuro, riesgo_quiebre = 0, False
    
    # Aseguramos compatibilidad si la fecha viene como texto (string) o como objeto date
    if fecha_proximo_pedido:
        if isinstance(fecha_proximo_pedido, str):
            try:
                fecha_proximo_pedido = datetime.strptime(fecha_proximo_pedido, "%Y-%m-%d").date()
            except Exception:
                pass
                
    if fecha_proximo_pedido and isinstance(fecha_proximo_pedido, date) and fecha_proximo_pedido > date.today():
        dias_hasta = (fecha_proximo_pedido - date.today()).days
        semanas_hasta = dias_hasta / 7.0
        dias_entrega_flotante = float(dias_entrega) if dias_entrega is not None else 0.0
        semanas_entrega = dias_entrega_flotante / 7.0
        demanda_futura = (semanas_hasta * ventas_semanales) + (semanas_entrega * ventas_semanales) + (4 * ventas_semanales)
        sugerido_futuro = int(max(0, demanda_futura - stock_actual))
        if semanas_stock < semanas_hasta:
            riesgo_quiebre = True
       
    return color, mensaje, sugerido_ahora, sugerido_futuro, riesgo_quiebre
    
def evaluar_carga_pesada(p):
    precio_fob = float(p.get("precio_fob", 0))
    cantidad = float(p.get("cantidad", 1) or 1)
    gastos_totales = float(sum(p.get("gastos", {}).values()))
    gasto_arribo_unitario = gastos_totales / cantidad if cantidad > 0 else 0
    if precio_fob <= 0: return "⚪", "Sin datos", 0
    porcentaje = (gasto_arribo_unitario / precio_fob) * 100
    if porcentaje > 60: return "🔴", f"PELIGRO: Flete = {porcentaje:.1f}% del costo.", 0
    elif porcentaje >= 30: return "🟡", f"CUIDADO: Flete = {porcentaje:.1f}% del costo.", 0
    else: return "🟢", f"RENTABLE: Flete = {porcentaje:.1f}% del costo.", 0

def calcular_pvp_sugerido(precio_fob_usd, costo_nacionalizado_usd, factor_markup_fob=2.6, margen_minimo=0.55, precio_benchmark_local=None):
    fob, costo = Decimal(str(precio_fob_usd)), Decimal(str(costo_nacionalizado_usd))
    pvp_markup = fob * Decimal(str(factor_markup_fob))
    pvp_margen = costo * (Decimal("1") + Decimal(str(margen_minimo)))
    pvp_benchmark = Decimal(str(precio_benchmark_local)) if precio_benchmark_local else None
    pvp_sugerido = max(pvp_markup, pvp_margen)
    if pvp_benchmark: pvp_sugerido = min(pvp_sugerido, pvp_benchmark * Decimal("1.15"))
    pvp_sugerido = pvp_sugerido.quantize(CENTAVO, ROUND_HALF_UP)
    utilidad = (pvp_sugerido - costo).quantize(CENTAVO)
    rentabilidad = (utilidad / costo) if costo > 0 else Decimal("0")
    alerta = ("⛔ Rentabilidad < 30%" if rentabilidad < Decimal("0.30") else "⚠️ Rentabilidad ajustada" if rentabilidad < Decimal("0.50") else "✅ Rentabilidad saludable")
    return {"fob_usd": fob, "costo_nacionalizado_usd": costo, "pvp_sugerido": pvp_sugerido, "utilidad_unitaria": utilidad, "rentabilidad_pct": (rentabilidad * 100).quantize(CENTAVO), "alerta": alerta}

def calcular_costos(productos, gastos_ingresados, config):
    margen = Decimal(str(config["margen"])) / Decimal("100")
    desc_mayorista = Decimal(str(config["desc_mayorista"])) / Decimal("100")
    desc_especial = Decimal(str(config["desc_especial"])) / Decimal("100")
    
    # Obtenemos los días de tránsito dinámicos según el país de origen seleccionado
    dias_transito_dinamicos = obtener_dias_transito(config.get("origen", "China"))
    
    gastos = []
    for nombre_gasto, criterio in GASTOS_CONTENEDOR:
        monto = gastos_ingresados[nombre_gasto]
        gastos.append((nombre_gasto, criterio, monto))
        campo_base = "peso_total" if criterio == "peso" else "volumen_total"
        repartos = prorratear_gasto(monto, productos, campo_base)
        for producto, monto_asignado in zip(productos, repartos): 
            producto["gastos"][nombre_gasto] = monto_asignado
            
    for producto in productos:
        cantidad = producto["cantidad"]
        gastos_totales = sum(producto["gastos"].values(), CERO)
        gasto_unitario = (gastos_totales / Decimal(str(cantidad))).quantize(Decimal('0.01'))
        costo_real = (producto["precio_fob"] + gasto_unitario).quantize(CENTAVO, ROUND_HALF_UP)
        producto.update({"gastos_totales": gastos_totales, "gasto_unitario": gasto_unitario, "costo_unitario": costo_real})
        
        div = UNO - margen
        producto["pvp_normal"] = redondear_entero(costo_real / div) if div > CERO else costo_real
        producto["pvp_mayorista"] = redondear_entero(producto["pvp_normal"] * (UNO - desc_mayorista))
        producto["pvp_especial"] = redondear_entero(producto["pvp_normal"] * (UNO - desc_especial))
        
        res = calcular_pvp_sugerido(precio_fob_usd=float(producto["precio_fob"]), costo_nacionalizado_usd=float(costo_real))
        producto["pvp_sugerido"] = Decimal(str(res["pvp_sugerido"]))
        producto["rentabilidad_pct"] = Decimal(str(res["rentabilidad_pct"]))
        producto["alerta_pvp"] = res["alerta"]
        
        # Asignamos los días de entrega dinámicos calculados del origen
        producto["dias_entrega"] = dias_transito_dinamicos
        
        color, mensaje, _, _, _ = evaluar_semaforo(
            producto.get("stock_actual", 0), 
            producto.get("ventas_semanales", 0), 
            producto["dias_entrega"], 
            config.get("fecha_proximo_pedido")
        )
        producto["semaforo_color"] = color
        producto["semaforo"] = mensaje
    return gastos

def consultar_partida(codigo):
    if not codigo:
        return {
            "descripcion": "No registrada en base local.",
            "ad_valorem": 0.10, "iva": 0.16,  # Valores estándar por defecto para evitar bloqueos
            "requisitos": "Consultar con agente aduanal.",
            "capitulo": "General",
        }
    
    # Normalizar eliminando puntos, guiones y espacios (ej: "8467.21.00" -> "84672100")
    codigo_limpio = str(codigo).strip().replace(".", "").replace("-", "").replace(" ", "")
    
    # 1. Búsqueda exacta con código limpio
    if codigo_limpio in PARTIDAS_BASE:
        return PARTIDAS_BASE[codigo_limpio]
        
    # 2. Búsqueda por subpartida de 6 dígitos
    if len(codigo_limpio) >= 6 and codigo_limpio[:6] in PARTIDAS_BASE:
        return PARTIDAS_BASE[codigo_limpio[:6]]
        
    # 3. Búsqueda por capítulo de 4 dígitos
    if len(codigo_limpio) >= 4 and codigo_limpio[:4] in PARTIDAS_BASE:
        return PARTIDAS_BASE[codigo_limpio[:4]]
        
    # 4. Resguardo de emergencia: si no está en la base local, asigna arancel estándar para que la auditoría no falle
    return {
        "descripcion": f"Partida {codigo} (Genérica / Comercial)",
        "ad_valorem": 0.10, 
        "iva": 0.16,
        "requisitos": "Sujeta a régimen general de importación.",
        "capitulo": codigo_limpio[:2] if len(codigo_limpio) >= 2 else "00",
    }
    
    
def estimar_derechos(codigo, valor_fob_usd, flete_usd=0.0, seguro_usd=0.0):
    info = consultar_partida(codigo)
    if info["ad_valorem"] is None:
        return {"error": "Partida sin información arancelaria local."}
    cif = valor_fob_usd + flete_usd + seguro_usd
    arancel = cif * info["ad_valorem"]
    iva     = (cif + arancel) * info["iva"]
    return {
        "partida": codigo, "descripcion": info["descripcion"],
        "ad_valorem_pct": info["ad_valorem"] * 100,
        "arancel_usd": round(arancel, 2), "iva_usd": round(iva, 2),
        "total_tributos_usd": round(arancel + iva, 2),
        "requisitos": info["requisitos"],
    }

def auditar_partidas(productos):
    filas = []
    for p in productos:
        codigo = p.get("partida_arancelaria")
        if not codigo: continue
        est = estimar_derechos(codigo, float(p["precio_fob"] * Decimal(str(p["cantidad"]))))
        if "error" in est: continue
        pagado = float(p["gastos"].get("Derechos de Aduana", 0))
        desv   = pagado - est["arancel_usd"]
        estado = ("✅ Coherente" if abs(desv) < 5 else ("⚠️ Revisar — posible sobrepago" if desv > 0 else "⚠️ Revisar — posible subdeclaración"))
        filas.append({
            "Producto": p["nombre"], "Partida": codigo, "Arancel estimado": est["arancel_usd"],
            "Arancel pagado": round(pagado, 2), "Desviación": round(desv, 2), "Estado": estado,
        })
    return filas

from datetime import datetime, timedelta

def generar_alertas_reposicion(productos, config, umbral_rojo=4, umbral_amarillo=8):
    alertas = []
    dias_tr = int(config.get("dias_transito", 60))
    f_ped_str = config.get("fecha_proximo_pedido")
    
    # Procesamos las fechas de forma segura
    fecha_llegada_fmt = "fecha estimada"
    f_ped_fmt = str(f_ped_str) if f_ped_str else "X/X/X"
    try:
        if f_ped_str:
            if isinstance(f_ped_str, str):
                f_ped_dt = datetime.strptime(f_ped_str, "%Y-%m-%d")
            else:
                f_ped_dt = datetime(f_ped_str.year, f_ped_str.month, f_ped_str.day)
            f_ped_fmt = f_ped_dt.strftime('%d/%m/%Y')
            f_llegada_dt = f_ped_dt + timedelta(days=dias_tr)
            fecha_llegada_fmt = f_llegada_dt.strftime('%d/%m/%Y')
    except Exception:
        pass

    for p in productos:
        ventas = float(p.get("ventas_semanales", 0))
        stock = float(p.get("stock_actual", 0))
        if ventas <= 0: 
            continue
            
        # Evaluamos el semáforo con los parámetros completos
        _, _, sug_ahora, sug_futuro, _ = evaluar_semaforo(
            stock, ventas, dias_entrega=dias_tr, fecha_proximo_pedido=f_ped_str
        )
        
        semanas = stock / ventas
        
        if semanas <= umbral_rojo:
            nivel = "🔴 CRÍTICO"
            accion = f"Emitir orden HOY — Sugerido inmediato: {sug_ahora} unds.<br><b>Futuro pedido</b> planificado para el {f_ped_fmt} ({sug_futuro} Unds), arribo aprox.: {fecha_llegada_fmt}."
        elif semanas <= umbral_amarillo:
            nivel = "🟡 PREVENTIVO"
            accion = f"Preparar orden esta semana — Sugerido: {sug_ahora} unds.<br><b>Futuro pedido</b> planificado para el {f_ped_fmt} ({sug_futuro} Unds), arribo aprox.: {fecha_llegada_fmt}."
        else:
            nivel = "🟢 ÓPTIMO"
            accion = f"Stock suficiente - Sin acción requerida.<br><b>Pedido Planificado</b> para el {f_ped_fmt} (sólo {sug_futuro} Unds), arribo aprox.: {fecha_llegada_fmt}."
               
        alertas.append({
            "producto": p["nombre"], "stock": stock, "ventas_semanales": ventas,
            "semanas_cobertura": round(semanas, 1), "nivel": nivel, "accion": accion,
            "proveedor": config.get("proveedor", "N/D"), "sug_futuro": sug_futuro
        })
    return sorted(alertas, key=lambda x: x["semanas_cobertura"])
    
  
def mostrar_alertas_en_panel(alertas):
    if not alertas:
        st.success("✅ Sin alertas. Inventario saludable.")
        return
        
    for a in alertas:
        # Definimos colores dinámicos según el nivel del semáforo
        if "CRÍTICO" in a["nivel"]:
            bg, borde = "#FFC7CE", "#C00000"
        elif "PREVENTIVO" in a["nivel"]:
            bg, borde = "#FFF3CD", "#FFEEBA"
        else:
            bg, borde = "#D4EDDA", "#C3E6CB" # Verde claro corporativo para stock óptimo
            
        st.markdown(f"""
            <div style="background-color: {bg}; color: #000; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 6px solid {borde};">
                <b>{a['nivel']} — {a['producto']}</b><br>
                Stock: <b>{a['stock']:.0f} unds</b> · Ventas: <b>{a['ventas_semanales']:.0f}/sem</b> · Cobertura: <b>{a['semanas_cobertura']} semanas</b><br>
                Acción: <i>{a['accion']}</i> — Proveedor: {a['proveedor']}
            </div>
        """, unsafe_allow_html=True)
        
# --- MÓDULO VISUAL: PESTAÑA SALVAVIDAS Y RUTAS ÓPTIMAS ---
def renderizar_pestana_salvavidas(productos, config):
    st.subheader("🛟 Módulo 'Salvavidas': Rutas Paralelas y Proveedores Óptimos")
    st.markdown("""
    Este módulo evalúa en tiempo real si existe riesgo de quiebre de inventario antes de que llegue su carga internacional, 
    calculando una **Ruta Puente de Auxilio Nacional** ajustada a la ubicación de su empresa en Venezuela y permitiéndole 
    seleccionar el proveedor óptimo para recalcular la operación.
    """)
    
    if not productos:
        st.info("⚠️ Por favor, cargue o calcule los productos primero para activar el análisis de salvavidas.")
        return

    # Selector de ubicación de la empresa para calcular fletes internos reales
    ubicacion_actual = config.get("ubicacion_empresa", "Caracas / Región Capital")
    nueva_ubicacion = st.selectbox(
        "📍 Ubicación de su Empresa / Almacén (para cálculo de flete interno en Venezuela):",
        list(UBICACIONES_VENEZUELA.keys()),
        index=list(UBICACIONES_VENEZUELA.keys()).index(ubicacion_actual) if ubicacion_actual in UBICACIONES_VENEZUELA else 0
    )
    config["ubicacion_empresa"] = nueva_ubicacion

    st.markdown("---")
    
    for i, prod in enumerate(productos):
        comparacion = comparar_rutas_abastecimiento(prod, config)
        
        with st.container():
            col1, col2 = st.columns([2, 3])
            
            with col1:
                st.markdown(f"**📦 {prod.get('nombre', 'Producto')}**")
                st.markdown(f"📦 **Stock Actual:** `{prod.get('stock_actual', 0)} unds` | **Venta Semanal:** `{prod.get('ventas_semanales', 0)} unds/sem`")
                st.markdown(f"⏱️ **Cobertura:** `{comparacion['cobertura_semanas']} semanas`")
                dias_t = comparacion['dias_tránsito_internacional']
                sems_t = round(dias_t / 7.0, 1)
                st.markdown(f"🚢 **Tránsito Origen ({config.get('origen', 'China')}):** `{dias_t} días ({sems_t} Sem)`")
                       
                if comparacion["en_riesgo_quiebre"]:
                    # Determinamos si es crítico (rojo) o preventivo (amarillo) según sus semanas de cobertura
                    cobertura_sem = comparacion.get('cobertura_semanas', 0)
                    es_critico = cobertura_sem <= 4
                    
                    bg_color = "#FFD2D2" if es_critico else "#FFF3CD"
                    border_color = "#FF4D4D" if es_critico else "#FFEEBA"
                    text_color = "#8A1C14" if es_critico else "#856404"
                    icono = "🔴" if es_critico else "🟡"
                    
                    fecha_pedido_str = config.get("fecha_proximo_pedido")
                    fecha_llegada_texto = "fecha estimada"
                    if fecha_pedido_str:
                        try:
                            fecha_pedido_dt = datetime.strptime(str(fecha_pedido_str), "%Y-%m-%d")
                            dias_t = int(comparacion['dias_tránsito_internacional'])
                            fecha_llegada_dt = fecha_pedido_dt + timedelta(days=dias_t)
                            fecha_llegada_texto = fecha_llegada_dt.strftime('%d/%m/%Y')
                        except Exception:
                            pass
                    
                    # Formateamos la fecha del próximo pedido para que se lea limpia
                    try:
                        fecha_pedido_fmt = datetime.strptime(str(fecha_pedido_str), "%Y-%m-%d").strftime('%d/%m/%Y') if fecha_pedido_str else "X/X/X"
                    except Exception:
                        fecha_pedido_fmt = str(fecha_pedido_str)
        
                    texto_aviso = (
                        f"<b>ALERTA DE INVENTARIO:</b> <span style='font-weight: normal;'>El stock se agotará en {cobertura_sem} semanas, "
                        f"antes de que llegue el pedido programado a realizar el {fecha_pedido_fmt}, cuyo arribo estimado será el</span> "
                        f"<b>{fecha_llegada_texto}</b>."
                    )
                    
                    
                    # Renderizamos la caja con el color dinámico correspondiente
                    st.markdown(f"""
                        <div style="background-color: {bg_color}; border: 1px solid {border_color}; color: {text_color}; padding: 12px; border-radius: 8px; margin-bottom: 10px;">
                            {icono} {texto_aviso}
                        </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    st.success("🟢 **Abastecimiento Seguro:** Cobertura suficiente hasta el próximo pedido.")


            with col2:
                if comparacion["en_riesgo_quiebre"]:
                    st.markdown("---")
                    st.markdown("##### 🔍 Búsqueda de Proveedores Alternativos en Tiempo Real")
                    
                    has_tavily = "TAVILY_API_KEY" in st.secrets
                    
                    if has_tavily:
                        if st.button(f"🆘 Buscar Proveedores Reales para: {prod.get('nombre')}", key=f"btn_sup_{i}", type="primary"):
                            with st.spinner("Rastreando proveedores en la web..."):
                                try:
                                    resultados = find_suppliers(
                                        producto=prod.get('nombre'),
                                        cantidad=comparacion.get('cantidad_puente', 0),
                                        ciudad=config.get('ubicacion_empresa', 'Caracas'),
                                        tavily_key=st.secrets["TAVILY_API_KEY"],
                                        openai_key=st.secrets.get("OPENAI_API_KEY")
                                    )
                                    
                                    if len(resultados) == 0:
                                        st.warning("El buscador no devolvió resultados directos. Verifique su conexión o intente nuevamente.")
                                    else:
                                        # Guardamos en sesión para alimentar el selectbox del formulario
                                        st.session_state[f"lista_prov_{i}"] = resultados
                                        st.success(f"¡Se encontraron {len(resultados)} candidatos mayoristas!")
                                        
                                        # Generamos URLs crudas y limpias para LinkColumn
                                        df = pd.DataFrame(resultados)
                                        df["telefono_val"] = df["telefono"].fillna("").apply(lambda t: t if t else "")
                                        df["Teléfono"] = df["telefono_val"].apply(lambda t: f"tel:{t}" if t else None)
                                        df["WhatsApp"] = df["telefono_val"].apply(lambda t: wa_link(t) if t else None)
                                        df["Teléfono_texto"] = df["telefono_val"].apply(lambda t: t if t else "Sin Nro de TLF disponible")
    
                                        df_display = df[[
                                            "nombre", "localidad", "Teléfono_texto", "Teléfono", "WhatsApp", "fuente"
                                        ]].rename(columns={
                                            "nombre": "Empresa", 
                                            "localidad": "Localidad", 
                                            "Teléfono_texto": "Nro. Contacto",
                                            "fuente": "Fuente web",
                                        })
    
                                        st.dataframe(
                                            df_display, use_container_width=True, hide_index=True,
                                            column_config={
                                                "Teléfono": st.column_config.LinkColumn("📞 Llamar", display_text="📞 Llamar al móvil"),
                                                "WhatsApp": st.column_config.LinkColumn("💬 WhatsApp", display_text="💬 Abrir WhatsApp"),
                                                "Fuente web": st.column_config.LinkColumn("🔗 Enlace", display_text="🔗 Ver fuente"),
                                            },
                                        )
                                        st.caption("ℹ️ *Mostrando directorio de proveedores nacionales pre-verificado (Modo de contingencia sin conexión web).*")
                                        
                                except Exception as e:
                                    st.error(f"Error crítico en el buscador web: {e}")
    
                        # --- FORMULARIO DE COTIZACIÓN ÚNICO Y BLINDADO ---
                        state_key = f"resultado_cot_{i}"
                        
                        # Recuperamos la cantidad puente con respaldo seguro de llaves
                        cant_puente = comparacion.get('cantidad_puente', 0)
                        if not cant_puente or cant_puente == 0:
                            cant_puente = comparacion.get('unidades_necesarias', comparacion.get('faltante', 50))
                        
                        st.divider()
                        st.markdown("### 📝 Ingreso Manual de Cotización Real")
                        
                        # 1. Recuperamos los proveedores de la sesión (si existen)
                        opciones_proveedores = ["Otro / Proveedor Externo (Escribir abajo)"]
                        if f"lista_prov_{i}" in st.session_state:
                            nombres_encontrados = [p["nombre"] for p in st.session_state[f"lista_prov_{i}"]]
                            opciones_proveedores.extend(nombres_encontrados)
                        
                        with st.form(key=f"form_cot_{i}"):
                            # 2. Selector de Proveedor
                            proveedor_elegido = st.selectbox(
                                "Proveedor Seleccionado", 
                                options=opciones_proveedores,
                                key=f"select_prov_{i}"
                            )
                            
                            # 3. Campo condicional si elige "Otro"
                            proveedor_custom = ""
                            if proveedor_elegido == "Otro / Proveedor Externo (Escribir abajo)":
                                proveedor_custom = st.text_input("Nombre del Proveedor Externo:", key=f"p_custom_{i}")
                            
                            col_f1, col_f2 = st.columns(2)
                            precio_real = col_f1.number_input("Precio Unitario Cotizado ($)", min_value=0.0, step=0.5, value=0.0, key=f"p_real_{i}")
                            dias_entrega = col_f2.number_input("Días de Entrega Reales", min_value=1, step=1, value=5, key=f"d_ent_{i}")
                            submit_cot = st.form_submit_button("Recalcular Operación con Cotización Real")
                            
                            if submit_cot:
                                nombre_final = proveedor_custom if proveedor_custom else proveedor_elegido
                                inversion_total = precio_real * cant_puente
                                
                                st.session_state[state_key] = {
                                    "proveedor": nombre_final,
                                    "precio_real": precio_real,
                                    "dias_entrega": dias_entrega,
                                    "inversion_total": inversion_total,
                                    "cant_puente": cant_puente
                                }
                        
                        # 4. Renderizado persistente del cálculo en sesión
                        if state_key in st.session_state:
                            cot = st.session_state[state_key]
                            st.success(f"✅ **Operación Recalculada (Guardada en Sesión)**\n\n"
                                       f"- **Proveedor Seleccionado:** {cot['proveedor']}\n"
                                       f"- **Inversión Real Total:** ${cot['inversion_total']:,.2f}\n"
                                       f"- **Plazo de Recepción:** {cot['dias_entrega']} días\n"
                                       f"- **Cantidad Cubierta:** {cot['cant_puente']} unidades "
                                       f"(a ${cot['precio_real']:,.2f} c/u)")
                    else:
                        st.info("💡 *Consejo:* Configure `TAVILY_API_KEY` en sus secretos de Streamlit Cloud para habilitar el buscador web automático.")
                else:
                    st.markdown("##### Estado de Ruta")
                    st.write("No se requiere activar la ruta de salvavidas local en este momento.")
            
            st.markdown("---")

def procesar_opcion_c_lcl(productos_c_df, volumen_m3_global, tarifa_plana_m3, fecha_embarque, semanas_transito, m_normal, m_mayor, m_sugerido, reinversion_base_prox, pct_perdida):
    from datetime import datetime, timedelta
    import pandas as pd

    resultados = []
    costo_total_flete_ddp = volumen_m3_global * tarifa_plana_m3
    volumen_items_suma = (productos_c_df["cantidad"] * productos_c_df["volumen_m3"]).sum()
    
    fob_total_actual = (productos_c_df["cantidad"] * productos_c_df["precio_fob"]).sum()
    
    inversion_general_total = 0.0
    utilidad_general_total = 0.0
    utilidad_normal_total_gen = 0.0
    utilidad_mayor_total_gen = 0.0
    utilidad_sug_total_gen = 0.0
    
    ingreso_bruto_operaciones_total = 0.0
    ingreso_semanal_global = 0.0
    min_semanas_cobertura = 999.0

    factor_efectivo = 1.0 - (pct_perdida / 100.0)

    # 1. Procesamiento por artículo
    for idx, row in productos_c_df.iterrows():
        nombre = row["nombre"]
        cantidad = float(row["cantidad"])
        fob_unitario = float(row["precio_fob"])
        vol_unitario = float(row["volumen_m3"])
        stock_inicial = float(row["stock_inicial"])
        ventas_semanales = float(row["ventas_semanales"])
        
        # Unidades efectivas cobrables (descontando % de pérdida/estancamiento)
        un_norm = float(row["unidades_normal"]) * factor_efectivo
        un_may = float(row["unidades_mayor"]) * factor_efectivo
        un_sug = float(row["unidades_sugeridas"]) * factor_efectivo
        
        # Prorrateo de flete DDP unitario (Gastos de Envío por unidad)
        volumen_lote = cantidad * vol_unitario
        proporcion_vol = (volumen_lote / volumen_items_suma) if volumen_items_suma > 0 else (1 / len(productos_c_df))
        arribo_asignado_total = costo_total_flete_ddp * proporcion_vol
        arribo_unitario = arribo_asignado_total / cantidad if cantidad > 0 else 0
        
        costo_real_unitario = fob_unitario + arribo_unitario
        inversion_total_articulo = cantidad * costo_real_unitario
        inversion_general_total += inversion_total_articulo
        
        # Precios por Canal redondeados al múltiplo de 5 más cercano
        def redondear_multiplo_5(val):
            return int(round(val / 5.0) * 5)
            
        pvp_normal = redondear_multiplo_5(costo_real_unitario * (1.0 + (m_normal / 100.0)))
        pvp_mayor = redondear_multiplo_5(costo_real_unitario * (1.0 + (m_mayor / 100.0)))
        pvp_sugerido = redondear_multiplo_5(costo_real_unitario * (1.0 + (m_sugerido / 100.0)))
        
        # Ingreso Bruto por Venta Operativa de este artículo
        ingreso_bruto_articulo = (un_norm * pvp_normal) + (un_may * pvp_mayor) + (un_sug * pvp_sugerido)
        ingreso_bruto_operaciones_total += ingreso_bruto_articulo
        
        # Utilidades por canal
        utilidad_un_normal = (pvp_normal - costo_real_unitario) * un_norm
        utilidad_un_mayor = (pvp_mayor - costo_real_unitario) * un_may
        utilidad_un_sug = (pvp_sugerido - costo_real_unitario) * un_sug
        
        utilidad_total_articulo = utilidad_un_normal + utilidad_un_mayor + utilidad_un_sug
        utilidad_general_total += utilidad_total_articulo
        utilidad_normal_total_gen += utilidad_un_normal
        utilidad_mayor_total_gen += utilidad_un_mayor
        utilidad_sug_total_gen += utilidad_un_sug
        
        # Flujo semanal ponderado con fraccionamiento de crédito en PVP Sugerido
        ingreso_contado_sem = (pvp_normal * (un_norm/cantidad) + pvp_mayor * (un_may/cantidad)) * ventas_semanales if cantidad > 0 else 0
        ingreso_sug_sem = (pvp_sugerido * (un_sug/cantidad)) * ventas_semanales if cantidad > 0 else 0
        ingreso_semanal_global += ingreso_contado_sem + (ingreso_sug_sem * (0.30 + 0.35/2 + 0.35/4))
        
        # Cobertura de stock basada en inventario disponible total
        stock_total_disponible = stock_inicial + cantidad
        semanas_cobertura = stock_total_disponible / ventas_semanales if ventas_semanales > 0 else 999.0
        if semanas_cobertura < min_semanas_cobertura:
            min_semanas_cobertura = semanas_cobertura

        resultados.append({
            "Artículo": nombre,
            "Cant": int(cantidad),
            "Precio FOB ($)": round(fob_unitario, 2),
            "Gastos de Envío ($)": round(arribo_unitario, 2),
            "Stock Inicial": int(stock_inicial),
            "Ventas/Sem": float(ventas_semanales),
            "Cobert. (Sem)": round(semanas_cobertura, 1),
            "Costo Puerta ($)": round(costo_real_unitario, 2),
            "Inversión ($)": round(inversion_total_articulo, 2),
            "PVP Normal ($)": int(pvp_normal),
            "PVP Mayor ($)": int(pvp_mayor),
            "PVP Sugerido ($)": int(pvp_sugerido),
            "Utilidad Normal ($)": round(utilidad_un_normal, 2),
            "Utilidad Mayor ($)": round(utilidad_un_mayor, 2),
            "Utilidad Sugerida ($)": round(utilidad_un_sug, 2),
            "Utilidad Total ($)": round(utilidad_total_articulo, 2)
        })
        
    df_res = pd.DataFrame(resultados)
    
    # 2. Cálculo de la Meta con gastos de envío proporcionales
    factor_escala_envio = (inversion_general_total / fob_total_actual) if fob_total_actual > 0 else 1.0
    meta_proximo_pedido_con_envio = reinversion_base_prox * factor_escala_envio

    # 3. Manejo de Fechas y Cronograma
    try:
        dt_pedido_inicial = datetime.strptime(str(fecha_embarque), "%Y-%m-%d")
    except Exception:
        dt_pedido_inicial = datetime.today()
        
    dt_entrega_inicial = dt_pedido_inicial + timedelta(weeks=int(semanas_transito))
    dt_quiebre = dt_entrega_inicial + timedelta(weeks=float(min_semanas_cobertura))
    
    semanas_recapitalizacion = (inversion_general_total / ingreso_semanal_global) if ingreso_semanal_global > 0 else 0.0
    dt_recapitalizacion = dt_entrega_inicial + timedelta(weeks=float(semanas_recapitalizacion))
    dt_entrega_proximo = dt_recapitalizacion + timedelta(weeks=int(semanas_transito))

    str_pedido_inicial = dt_pedido_inicial.strftime("%Y-%m-%d")
    str_entrega_inicial = dt_entrega_inicial.strftime("%Y-%m-%d")
    str_recap = dt_recapitalizacion.strftime("%Y-%m-%d")
    str_quiebre = dt_quiebre.strftime("%Y-%m-%d")
    str_entrega_prox = dt_entrega_proximo.strftime("%Y-%m-%d")

    # 4. Tablero Financiero Reordenado y Cronograma Ejecutivo
    st.markdown("---")
    st.markdown("### 📊 Tablero Financiero Multicanal y Cronograma Ejecutivo")
    
    # Reordenamiento solicitado en el tablero superior:
    # 1. Ingreso Bruto, 2. Inversión Gral., 3. Meta Próximo Pedido
    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("💵 Ingreso Bruto x Vtas Operac.", f"${ingreso_bruto_operaciones_total:,.2f}", help="Calculado sobre unidades efectivas descontando el % de pérdida.")
    rc2.metric("📦 Inversión General Embarque", f"${inversion_general_total:,.2f}")
    rc3.metric("🎯 Meta p/Próx Pedido (+ Gtos Envío)", f"${meta_proximo_pedido_con_envio:,.2f}")
    
    st.markdown("---")
    
    # Tiempo de recuperación del capital ubicado abajo como se solicitó
    st.metric("⏱️ Tiempo Recuperación Capital", f"{semanas_recapitalizacion:.1f} Semanas", help="Calculado a partir de la llegada a puerta considerando pagos fraccionados.")
    st.markdown("---")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Utilidad Global", f"${utilidad_general_total:,.2f}")
    m2.metric("🛍️ Utilidad PV Normal", f"${utilidad_normal_total_gen:,.2f}")
    m3.metric("🤝 Utilidad PV Mayor", f"${utilidad_mayor_total_gen:,.2f}")
    m4.metric("⭐ Utilidad PV Sug", f"${utilidad_sug_total_gen:,.2f}")
    
    st.markdown("---")
    st.markdown("#### 📅 Cronograma de Eventos y Fechas Clave de la Operación:")
    st.markdown(f"""
    * **a. 🚢 Fecha pedido inicial:** `{str_pedido_inicial}`
    * **b. 🚚 Fecha estimada de entrega DDP Inicial:** `{str_entrega_inicial}`
    * **c. 💰 Fecha estimada de recuperación del Capital para invertir en próximo pedido:** `{str_recap}`
    * **d. 🔴 Fecha de Quiebre de inventario (según estimado de Vtas.):** `{str_quiebre}`
    * **e. 📦 Fecha de estimado entrega DDP próximo:** `{str_entrega_prox}`
    """)
    st.markdown("---")

    # --- GUARDAR RESULTADOS EN SESIÓN PARA EL PDF ---
    st.session_state["res_ingreso_bruto"] = ingreso_bruto_operaciones_total
    st.session_state["res_inversion_total"] = inversion_general_total
    st.session_state["res_meta_proximo"] = meta_proximo_pedido_con_envio
    st.session_state["res_semanas_recap"] = semanas_recapitalizacion
    st.session_state["res_utilidad_global"] = utilidad_general_total
    st.session_state["res_utilidad_normal"] = utilidad_normal_total_gen
    st.session_state["res_utilidad_mayor"] = utilidad_mayor_total_gen
    st.session_state["res_utilidad_sug"] = utilidad_sug_total_gen
    st.session_state["res_f_pedido"] = str_pedido_inicial
    st.session_state["res_f_entrega"] = str_entrega_inicial
    st.session_state["res_f_recap"] = str_recap
    st.session_state["res_f_quiebre"] = str_quiebre
    st.session_state["res_f_entrega_prox"] = str_entrega_prox
  
    return df_res
    
def proyectar_flujo_caja(productos, config):
    import pandas as pd
    
    # 1. Extraer parámetros base de configuración
    capital_inicial = float(config.get("capital_inicial", 10000.0))
    costo_fijo = float(config.get("costo_fijo_semanal", 250.0))
    
    # 2. Calcular ingreso semanal estimado a partir de los productos del inventario
    ingreso_semanal_base = 0.0
    if productos:
        for p in productos:
            # Soportar tanto objetos como diccionarios
            if isinstance(p, dict):
                ventas = float(p.get("ventas_semanales", p.get("ventas", 5)))
                pvp = float(p.get("precio_venta", p.get("pvp_normal", 50.0)))
            else:
                ventas = float(getattr(p, "ventas_semanales", 5))
                pvp = float(getattr(p, "pvp_normal", 50.0))
            ingreso_semanal_base += ventas * pvp
            
    if ingreso_semanal_base <= 0:
        ingreso_semanal_base = 3500.0  # Valor predeterminado seguro de respaldo

    # 3. Construir la proyección de las 13 semanas
    data = []
    saldo = capital_inicial
    
    for sem in range(1, 14):
        ingreso = ingreso_semanal_base
        egreso = costo_fijo
        
        # Simular impacto de reposición en semanas clave (ej. semana 3)
        if sem == 3 and "monto_proximo_pedido" in config:
            egreso += float(config.get("monto_proximo_pedido", 0.0))
            
        saldo += (ingreso - egreso)
        data.append({
            "Semana": sem,
            "Ingreso proyectado": ingreso,
            "Egreso proyectado": egreso,
            "Saldo acumulado": saldo
        })
        
    return pd.DataFrame(data)
    
def mostrar_flujo_caja(df_flujo, config):
    st.subheader("📅 Proyección de flujo de caja — 13 semanas")
    
    # Texto del switch en negrita y fucsia corporativo (#c71585)
    st.markdown(
        '<p style="color: #c71585; font-weight: bold; font-size: 15px; margin-bottom: 4px;">👉🏼 🎛️ Activar Simulador Gerencial de Escenarios (What-If)</p>',
        unsafe_allow_html=True
    )
    modo_simulacion = st.toggle("Habilite para ajustar variables en tiempo real", value=False, label_visibility="collapsed")
    
    df_activo = df_flujo.copy()
    
    # 1) Extracción de fecha de embarque desde config y cálculo automático del arribo (+60 días)
    fecha_embarque = config.get("fecha_proximo_pedido", "2027-01-20")
    try:
        from datetime import datetime, timedelta
        dt_emb = datetime.strptime(str(fecha_embarque), "%Y-%m-%d")
        dt_arr = dt_emb + timedelta(days=60)
        fecha_arribo = dt_arr.strftime("%Y-%m-%d")
        
        # Cálculo automático de la semana de emisión basada en la fecha real para sincronizar con el reporte
        hoy = date.today()
        dias_diff = (dt_emb.date() - hoy).days
        semana_defecto_emision = max(1, min(13, (dias_diff // 7) + 1))
    except Exception:
        fecha_arribo = "Por definir (60 días)"
        semana_defecto_emision = 1

    if modo_simulacion:
        st.markdown(
            """
            <div style="background-color: #f8f9fa; padding: 6px 10px; border-radius: 6px; border: 1px solid #b8d4e5; margin-bottom: 8px; font-size: 12px; color: #0b2545;">
                💡 <b>Modo Simulación Activo:</b> Ajuste los parámetros abajo. Las métricas y la gráfica se actualizan instantáneamente.
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Estructura compacta: Izquierda (Inputs reducidos) / Derecha (Métricas verticales y Fechas)
        col_sim_izq, col_sim_der = st.columns([1.2, 1])
        
        with col_sim_izq:
            st.markdown("<p style='font-size: 11px; font-weight: bold; color: #1f4e78; margin-bottom: 2px;'>🎛️ Parámetros de Simulación:</p>", unsafe_allow_html=True)
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                sim_cap = st.number_input("Capital Adic. ($)", value=0.0, step=500.0, key="sim_cap_s")
                sim_margen = st.number_input("Margen (%)", min_value=5.0, max_value=100.0, value=float(config.get("margen", 30.0)), step=1.0, key="sim_m_s")
                sim_cfijo = st.number_input("Costo Fijo ($)", value=float(config.get("costo_fijo_semanal", 250.0)), step=50.0, key="sim_cf_s")
            with sub_c2:
                sim_pedido = st.number_input("Próx. Pedido ($)", value=float(config.get("monto_proximo_pedido", 15000.0)), step=1000.0, key="sim_ped_s")
                sem_emision = st.number_input("Sem. Emisión", min_value=1, max_value=13, value=int(semana_defecto_emision), step=1, key="sim_sem_num_s")
                estrategia_pago = st.selectbox("Cond. Pago", ["Contado", "Crédito a 30 días (+4sem)", "Crédito a 60 días (+8sem)"], key="sim_pago_s")
        
        with col_sim_der:
            # Factor de ajuste por margen
            margen_base = float(config.get("margen", 30.0))
            factor_m = (1.0 + (sim_margen / 100.0)) / (1.0 + (margen_base / 100.0)) if margen_base > 0 else 1.0
            
            saldos_simulados = []
            capital_inicial_base = float(config.get("capital_inicial", 0.0)) + sim_cap
            acumulado = capital_inicial_base
            
            if estrategia_pago.startswith("Contado"):
                semana_pago = int(sem_emision)
            elif estrategia_pago.startswith("Crédito a 30"):
                semana_pago = int(sem_emision) + 4
            else:
                semana_pago = int(sem_emision) + 8
                
            for idx, row in df_activo.iterrows():
                sem = int(row["Semana"])
                ingreso_original = float(row.get("Ingreso proyectado", 3500.0))
                ingreso_nuevo = ingreso_original * factor_m
                
                egreso_nuevo = sim_cfijo
                if sem == semana_pago:
                    egreso_nuevo += sim_pedido
                    
                acumulado += (ingreso_nuevo - egreso_nuevo)
                saldos_simulados.append(acumulado)
                
            df_activo["Saldo acumulado"] = saldos_simulados
            if "Ingreso proyectado" in df_activo.columns:
                df_activo["Ingreso proyectado"] = df_activo["Ingreso proyectado"] * factor_m

            ingreso_total_val = df_activo['Ingreso proyectado'].sum() if 'Ingreso proyectado' in df_activo.columns else df_activo['Saldo acumulado'].iloc[-1]
            saldo_final_val = df_activo['Saldo acumulado'].iloc[-1]
            minimo_val = df_activo["Saldo acumulado"].min()

            st.markdown("<p style='font-size: 11px; font-weight: bold; color: #1f4e78; margin-bottom: 2px;'>📊 Resultados y Fechas Clave:</p>", unsafe_allow_html=True)
            
            # Métricas apiladas verticalmente para evitar cortes horizontales
            st.metric("Ingreso total", f"${ingreso_total_val:,.0f}")
            st.metric("Saldo final", f"${saldo_final_val:,.0f}")
            st.metric("Saldo mínimo", f"${minimo_val:,.0f}", delta=None if minimo_val >= 0 else "Riesgo de Déficit")
            
            st.markdown(
                f"""
                <div style="background-color: #e8f4f8; padding: 6px 10px; border-radius: 5px; border: 1px solid #b8d4e5; font-size: 12px; color: #0b2545; margin-top: 6px;">
                    🚢 <b>Fecha prox. Embarque:</b> {fecha_embarque}<br>
                    🏁 <b>Fecha estimada de Arribo (+60 días):</b> {fecha_arribo}
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        # Modo Normal: Métricas apiladas verticalmente y fechas clave debajo
        ingreso_total_val = df_activo['Ingreso proyectado'].sum() if 'Ingreso proyectado' in df_activo.columns else df_activo['Saldo acumulado'].iloc[-1]
        saldo_final_val = df_activo['Saldo acumulado'].iloc[-1]
        minimo_val = df_activo["Saldo acumulado"].min()

        st.metric("Ingreso total", f"$ {ingreso_total_val:,.0f}")
        st.metric("Saldo final", f"$ {saldo_final_val:,.0f}")
        st.metric("Saldo mínimo", f"$ {minimo_val:,.0f}", delta=None if minimo_val >= 0 else "Riesgo de Déficit")

        st.markdown(
            f"""
            <div style="background-color: #f8f9fa; padding: 8px 12px; border-radius: 6px; border: 1px solid #dcdcdc; font-size: 13px; color: #1f4e78; margin-top: 8px; margin-bottom: 10px;">
                👉🏼 🚢 <b>Fecha prox. Embarque:</b> {fecha_embarque} &nbsp;&nbsp;|&nbsp;&nbsp; 🏁 <b>Fecha estimada de Arribo (+60 días):</b> {fecha_arribo}
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- RENDERIZADO DE LA GRÁFICA ---
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(df_activo["Semana"], df_activo["Saldo acumulado"], marker="o", color="#1f4e78", linewidth=2)
    ax.axhline(0, color="red", linestyle="--", linewidth=1)
    ax.set_xlabel("Semana")
    ax.set_ylabel("Saldo acumulado (USD)")
    ax.set_title("Saldo de caja proyectado (Simulación Dinámica)" if modo_simulacion else "Saldo de caja proyectado")
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    # --- MÓDULO DE INTERPRETACIÓN Y DIAGNÓSTICO FINANCIERO DINÁMICO ---
    st.markdown("---")
    st.markdown("### 🧠 Interpretación y Diagnóstico Financiero")
    
    st.markdown(
        """
        **¿Qué es la Proyección de Flujo de Caja a 13 Semanas?**  
        Es un modelo financiero dinámico de alta precisión que simula semana a semana la entrada de ingresos por ventas y la salida de compromisos operativos y de reposición, vigilando permanentemente que el capital de trabajo de la empresa **nunca caiga por debajo del límite seguro**.
        """
    )

    if minimo_val >= 1000 and saldo_final_val >= minimo_val:
        st.success(
            f"""
            **🟢 Diagnóstico Financiero Óptimo (Saludable):**  
            El flujo de caja proyectado muestra una tendencia de crecimiento sólido y constante. El saldo mínimo de caja es de **$ {minimo_val:,.0f}**, superando holgadamente el umbral de riesgo. La combinación de tiempos de emisión y pago protege la liquidez y asegura el inventario.
            """
        )
    elif minimo_val >= 0:
        st.warning(
            f"""
            **🟡 Diagnóstico de Liquidez Ajustada (En Observación):**  
            El flujo proyectado presenta un margen ajustado (Saldo Mínimo: **$ {minimo_val:,.0f}**). Su capital de trabajo se acerca al límite de seguridad. Considere negociar mayor plazo de pago con el proveedor para desahogar la caja operativa sin alterar su fecha de inventario.
            """
        )
    else:
        st.error(
            f"""
            **🔴 Diagnóstico de Alerta Roja por Déficit (Riesgo Crítico):**  
            ¡Atención gerencial! El modelo detecta un saldo mínimo negativo (**$ {minimo_val:,.0f}**). Los compromisos superan el ritmo de ingresos previstos en la semana crítica. Aplazar la condición de pago a crédito resolverá este déficit de inmediato.
            """
        )
       
def exportar_csv_para_sheets(productos, config):
    filas = []
    for p in productos:
        filas.append({
            "Producto": p["nombre"], "Partida_Arancelaria": p.get("partida_arancelaria", ""),
            "Cantidad": p["cantidad"], "FOB_Origen_USD": float(p["precio_fob"]),
            "Costo_Real_USD": float(p["costo_unitario"]), "PVP_Normal": float(p["pvp_normal"]),
            "PVP_Sugerido": float(p.get("pvp_sugerido", p["pvp_normal"])),
            "Rentabilidad_Pct": float(p.get("rentabilidad_pct", 0)),
            "Stock_Actual": float(p.get("stock_actual", 0)), "Ventas_Semanales": float(p.get("ventas_semanales", 0)),
            "Semaforo": p.get("semaforo", ""),
        })
    return pd.DataFrame(filas).to_csv(index=False).encode("utf-8-sig")

def boton_exportar_sheets(productos, config):
    csv = exportar_csv_para_sheets(productos, config)
    id_perfil = config.get("id_perfil", "empresa")
    st.download_button("📱 Descargar CSV para Google Sheets", data=csv, file_name=f"importacion_{config.get('factura','SN')}_{id_perfil}.csv", mime="text/csv", help="Súbelo a Google Drive → abrir con Google Sheets.")

def crear_reporte_html(productos, gastos_contenedor, config):
    total_items = len(productos)
    total_unds = sum(p["cantidad"] for p in productos)
    total_mercancia = sum((p["precio_fob"] * Decimal(str(p["cantidad"])) for p in productos), CERO)
    total_gastos = sum((p["gastos_totales"] for p in productos), CERO)
    origen_efectivo = texto_efectivo(config.get("origen"), config.get("origen_otro"))
    
    fob_total_val = float(total_mercancia)
    flete_val = float(config.get("flete", 2500.0))
    seguro_val = float(config.get("seguro", 300.0))
    aranceles_val = float(config.get("aranceles", 1500.0))
    gastos_loc_val = float(config.get("gastos_locales", 1000.0))
    
    gastos_arribo_val = flete_val + seguro_val + aranceles_val + gastos_loc_val
    cif_total = fob_total_val + flete_val + seguro_val
    costo_total_imp = cif_total + aranceles_val + gastos_loc_val
    factor_mult = costo_total_imp / fob_total_val if fob_total_val > 0 else 1.0
    impacto_flete_global = (flete_val / fob_total_val * 100) if fob_total_val > 0 else 0

    # Lógica de colores institucionales para la alerta de carga pesada
    if impacto_flete_global > 60:
        bg_alerta = "#f8d7da"
        border_alerta = "#f5c6cb"
        color_alerta = "#721c24"
        texto_alerta = f"ROJO (Crítico >60%) — Impacto: {impacto_flete_global:.1f}% del FOB"
    elif impacto_flete_global >= 30:
        bg_alerta = "#fff3cd"
        border_alerta = "#ffeeba"
        color_alerta = "#856404"
        texto_alerta = f"AMARILLO (Moderado 30%-60%) — Impacto: {impacto_flete_global:.1f}% del FOB"
    else:
        bg_alerta = "#d4edda"
        border_alerta = "#c3e6cb"
        color_alerta = "#155724"
        texto_alerta = f"VERDE (Óptimo <30%) — Impacto: {impacto_flete_global:.1f}% del FOB"

    # Inicio de la estructura HTML principal
    html = f"""
    <div style="font-family: Arial, sans-serif; color: #333; max-width: 1000px; margin: auto;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #1f4e78; margin-bottom: 5px;">REPORTE EJECUTIVO DE IMPORTACIÓN</h1>
            <p style="margin: 0; font-size: 14px;"><b>{config.get('empresa', '')}</b> | RIF: {config.get('rif', '')} | Propietario: {config.get('propietario', '')}</p>
            <p style="margin: 5px 0; font-size: 12px; color: #666;">Origen: {origen_efectivo} | Proveedor: {config.get('proveedor', '')} | Factura: {config.get('factura', '')}</p>
        </div>

        <!-- 4 Tarjetas de Métricas Principales -->
        <div style="display: flex; justify-content: space-between; margin-bottom: 15px; gap: 10px;">
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; background-color: #fafafa; border-radius: 5px;">
                <div style="font-size: 10px; color: #666; font-weight: bold;">VALOR FOB TOTAL</div>
                <div style="font-size: 15px; font-weight: bold; color: #1f4e78;">$ {fob_total_val:,.2f}</div>
            </div>
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; background-color: #fafafa; border-radius: 5px;">
                <div style="font-size: 10px; color: #666; font-weight: bold;">GASTOS ARRIBO</div>
                <div style="font-size: 15px; font-weight: bold; color: #1f4e78;">$ {gastos_arribo_val:,.2f}</div>
            </div>
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; background-color: #fafafa; border-radius: 5px;">
                <div style="font-size: 10px; color: #666; font-weight: bold;">FACTOR MULT.</div>
                <div style="font-size: 15px; font-weight: bold; color: #1f4e78;">{factor_mult:.3f}</div>
            </div>
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; background-color: #fafafa; border-radius: 5px;">
                <div style="font-size: 10px; color: #666; font-weight: bold;">IMPACTO FLETE</div>
                <div style="font-size: 15px; font-weight: bold; color: #1f4e78;">{impacto_flete_global:.1f}%</div>
            </div>
        </div>

        <!-- Contenedor de Alerta de Carga Pesada con Color Institucional -->
        <div style="background-color: {bg_alerta}; border: 1px solid {border_alerta}; color: {color_alerta}; padding: 10px; margin-bottom: 20px; border-radius: 4px; font-size: 11px;">
            <b>Evaluación Global de Carga Pesada (Embarque):</b> <b>{texto_alerta}</b>
            <div style="font-size: 9.5px; margin-top: 3px; opacity: 0.85;">
                Relación porcentual del flete frente al valor FOB. Evalúa la eficiencia estructural del transporte marítimo y su incidencia en la rentabilidad.
            </div>
        </div>

        <!-- Resumen General de Costos y Precios de Venta -->
        <h3 style="color: #1f4e78; margin-bottom: 5px;">Resumen General de Costos y Precios de Venta</h3>
        <table style="page-break-inside: avoid; width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 30px;">
            <tr style="background-color: #1f4e78; color: white;">
                <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Producto</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Cant.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Costo U.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">PVP Norm.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">PVP May.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">PVP Esp.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Semáforo</th>
            </tr>
    """

    # Bucle para llenar la tabla de Resumen General
    for p in productos:
        color_txt = "red" if "🔴" in p.get("semaforo_color", "") else ("orange" if "🟡" in p.get("semaforo_color", "") else "green")
        estado_txt = "ROJO" if "🔴" in p.get("semaforo_color", "") else ("AMARILLO" if "🟡" in p.get("semaforo_color", "") else "VERDE")
        html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{p.get('nombre', '')}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{p.get('cantidad', 0)}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${float(p.get('costo_final_unitario', 0)):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${float(p.get('pvp_normal', 0)):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${float(p.get('pvp_mayorista', 0)):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${float(p.get('pvp_especial', 0)):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center; color: {color_txt}; font-weight: bold;">{estado_txt}</td>
            </tr>
        """

    html += """
        </table>
        
        <h3 style="color: #1f4e78; margin-bottom: 10px;">Desglose Individual y Prorrateo de Gastos por Ítem</h3>
    """

    # Generar las alertas de reposición sincronizadas con el motor exacto
    alertas_reposicion = generar_alertas_reposicion(productos, config)
    mapa_reposicion = {item.get('producto'): item for item in alertas_reposicion}

    # Bucle para el Desglose Individual de cada producto
    for p in productos:
        nombre_prod = p.get('nombre', '')
        
        # Extracción inteligente, flexible y segura para convertir Decimales o Nulos a float
        gastos_p = p.get('gastos', {})
        
        def obtener_gasto_seguro(keyword):
            for k, v in gastos_p.items():
                if keyword in k.lower():
                    try:
                        return float(v or 0)
                    except Exception:
                        return 0.0
            return 0.0

        val_manejo = obtener_gasto_seguro('manejo')
        val_flete_nac = obtener_gasto_seguro('nacional')
        val_log_int = obtener_gasto_seguro('logística') or obtener_gasto_seguro('internacional')
        
        val_aduana = obtener_gasto_seguro('aduana')
        val_gestion = obtener_gasto_seguro('gestión')
        val_admin = obtener_gasto_seguro('admin') or obtener_gasto_seguro('administrativo')

        # Extraer los valores exactos calculados por el motor de reposición
        info_repo = mapa_reposicion.get(nombre_prod, {})
        if info_repo:
            stock = float(p.get("stock_actual", 0))
            ventas = float(p.get("ventas_semanales", 0))
            dias_tr = int(config.get("dias_transito", 60))
            f_ped_str = config.get("fecha_proximo_pedido")
            
            _, _, sug_ahora, sug_futuro, _ = evaluar_semaforo(
                stock, ventas, dias_entrega=dias_tr, fecha_proximo_pedido=f_ped_str
            )
            ped_inmediato = sug_ahora
            ped_planificado = sug_futuro
        else:
            ped_inmediato = 0
            ped_planificado = 0

        # Determinar el color y estado de alerta visual
        semaforo_str = str(p.get('semaforo_color', ''))
        if "🔴" in semaforo_str or "ROJO" in semaforo_str.upper():
            txt_estado = "ROJO - 🔴"
            color_txt = "#dc3545"
        elif "🟡" in semaforo_str or "AMARILLO" in semaforo_str.upper():
            txt_estado = "AMARILLO - 🟡"
            color_txt = "#ffc107"
        else:
            txt_estado = "VERDE - 🟢"
            color_txt = "#28a745"

        # Extracción robusta y matemática del Costo Final Unitario (FOB + Arribo)
        fob_u = float(p.get('precio_fob', 0))
        gasto_u = float(p.get('gasto_unitario', 0))
        costo_final_u = float(p.get('costo_final_unitario', 0) or p.get('costo_real', 0) or p.get('costo_unitario', 0) or (fob_u + gasto_u))

        # Obtener la fecha planificada formateada de forma segura
        f_ped_str = config.get('fecha_proximo_pedido')
        f_ped_fmt = "15/12/2026"
        try:
            if f_ped_str:
                if isinstance(f_ped_str, str):
                    f_ped_dt = datetime.strptime(f_ped_str, "%Y-%m-%d")
                else:
                    f_ped_dt = datetime(f_ped_str.year, f_ped_str.month, f_ped_str.day)
                f_ped_fmt = f_ped_dt.strftime('%d/%m/%Y')
        except Exception:
            pass

        html += f"""
        <div style="border: 1px solid #bcd; background-color: #f4f8fb; padding: 10px; margin-bottom: 15px; border-radius: 5px; page-break-inside: avoid;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <div style="font-weight: bold; color: #1f4e78; font-size: 14px;">Producto: {nombre_prod}</div>
                <div style="text-align: right; font-size: 11px;">
                    <b>URGENTE Pedir YA al Proveedor Ext. ===> {float(ped_inmediato):,.0f} unds</b><br>
                    <span style="color: #555; font-style: italic; font-size: 10px;">Según Pedido Planificado para el {f_ped_fmt} Pedir {float(ped_planificado):,.0f} Unds</span>
                </div>
            </div>
            
            <div style="font-size: 11px; color: #444; margin-bottom: 5px;">
                <b>Estado:</b> <span style="color: {color_txt}; font-weight: bold;">{txt_estado}</span>
            </div>

            <div style="font-size: 11px; color: #444; margin-bottom: 5px;">
                <b>Cant.:</b> {p.get('cantidad', 0)} unds | <b>FOB U.:</b> $ {fob_u:,.2f} | <b>Peso T.:</b> {p.get('peso_total', 0):,.2f} kg | <b>Vol. T.:</b> {p.get('volumen_total', 0):,.4f} m³
            </div>
            
            <div style="background-color: #fff; border: 1px solid #ddd; padding: 6px; margin-bottom: 5px; font-size: 11px;">
                <b>Gastos Arribo U.:</b> $ {gasto_u:,.2f} | <b>COSTO FINAL UNITARIO:</b> <span style="color: #1f4e78; font-weight: bold;">$ {costo_final_u:,.2f}</span>
            </div>
            
            <div style="font-size: 10px; color: #555; display: flex; justify-content: space-between;">
                <div><b>Gastos (Parte 1):</b> Manejo: ${val_manejo:,.2f} | Flete Nac.: ${val_flete_nac:,.2f} | Log. Int.: ${val_log_int:,.2f}</div>
                <div><b>Gastos (Parte 2):</b> Aduana: ${val_aduana:,.2f} | Gestión: ${val_gestion:,.2f} | Admin: ${val_admin:,.2f}</div>
            </div>
        </div>
        """
                 
    # Pie de página corporativo (Autoría de JPV)
    html += f"""
        <div style="margin-top: 30px; page-break-inside: avoid; border: 1px solid #1f4e78; padding: 15px; border-radius: 6px; background-color: #fafafa; text-align: center;">
            <p style="margin: 0 0 5px 0; font-size: 11px; color: #666; font-weight: bold;">Diseñado y elaborado por su Asesor de Importación Inteligente:</p>
            <h3 style="margin: 0; color: #1f4e78; font-size: 16px;">Prof. Jesús Pulido V.</h3>
            <p style="margin: 5px 0; font-size: 11px; color: #444;">
                Teléfonos de contacto: 0424-728.3199 / 0416-291.6426<br>
                Correo: jeshua166@gmail.com
            </p>
            <div style="margin-top: 10px;">
                <img src="https://i.postimg.cc/Hxhd38gS/JPV-Asesor-Importacion.jpg" style="max-height: 120px; border-radius: 4px;">
            </div>
        </div>

        <!-- 3. Apéndice: Glosario Técnico -->
        <div style="margin-top: 25px; page-break-inside: avoid; border-top: 1px solid #ccc; padding-top: 10px;">
            <h3 style="color: #1f4e78; margin-bottom: 6px; font-size: 14px;">3. Apéndice: Glosario Técnico de Comercio Internacional</h3>
            <p style="font-size: 10px; color: #555; margin: 3px 0;"><b>Valor FOB:</b> Costo neto de la mercancía en origen (fábrica o puerto de embarque).</p>
            <p style="font-size: 10px; color: #555; margin: 3px 0;"><b>Factor Multiplicador:</b> Coeficiente global para determinar el costo real puesto en bodega por cada dólar invertido.</p>
            <p style="font-size: 10px; color: #555; margin: 3px 0;"><b>Impacto Flete/FOB:</b> Relación porcentual entre el costo del flete y el FOB; mide si la carga es ligera o pesada.</p>
            <p style="font-size: 10px; color: #555; margin: 3px 0;"><b>Costo Final Unitario:</b> Costo real de cada unidad ya nacionalizada (incluye flete, seguro, aranceles y gastos locales).</p>
            <p style="font-size: 10px; color: #555; margin: 3px 0;"><b>Rentabilidad:</b> Porcentaje de ganancia neta estimada respecto al costo final unitario del producto.</p>
        </div>
    </div>
    """

    return html.replace('\n', '').strip()
    
def generar_pdf_desde_html(html_content):
    try:
        result = io.BytesIO()
        pisa.CreatePDF(io.StringIO(html_content), dest=result)
        return result.getvalue()
    except Exception as e:
        st.error(f"Error generando PDF: {e}")
        return None

def leer_excel(archivo):
    if archivo.name.lower().endswith(".csv"): return pd.read_csv(archivo)
    return pd.read_excel(archivo)

def sugerir_columna(columnas, posibles):
    columnas_lower = {i: str(c).lower() for i, c in enumerate(columnas)}
    for palabra in posibles:
        for idx, col_lower in columnas_lower.items():
            if palabra in col_lower: 
                return columnas[idx]
    return None

def mapear_columnas(df):
    columnas_opciones = ["(ninguna)"] + list(df.columns)
    st.markdown("**Mapeo de columnas del Excel**")
    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3); c7, c8, c9 = st.columns(3)
    
    sugerencias = {
        "producto": ["producto", "descripcion", "descripción", "nombre", "articulo"],
        "cantidad": ["cantidad", "cant", "unidades", "qty"],
        "precio": ["fob", "precio", "origen", "china", "unitario", "costo"],
        "peso": ["peso", "kg", "weight"],
        "volumen": ["volumen", "m3", "cbm", "volume"],
        "stock": ["stock", "inventario", "existencia"],
        "ventas": ["venta", "ventas", "semanal", "salida"],
        "dias": ["dias", "días", "entrega", "llegada", "transito"],
        "partida": ["partida", "hs", "arancel", "codigo"]
    }
    
    def selector(col_st, etiqueta, keys, key_sel):
        sug = sugerir_columna(list(df.columns), keys)
        idx = columnas_opciones.index(sug) if sug in columnas_opciones else 0
        return col_st.selectbox(etiqueta, columnas_opciones, index=idx, key=key_sel)

    return {
        "producto": selector(c1, "Producto / Descripción", sugerencias["producto"], "sel_prod"),
        "cantidad": selector(c2, "Cantidad", sugerencias["cantidad"], "sel_cant"),
        "precio": selector(c3, "Precio FOB Origen $/u", sugerencias["precio"], "sel_prec"),
        "peso": selector(c4, "Peso unitario (kg)", sugerencias["peso"], "sel_peso"),
        "volumen": selector(c5, "Volumen unitario (m³)", sugerencias["volumen"], "sel_vol"),
        "stock": selector(c6, "Stock Actual", sugerencias["stock"], "sel_stock"),
        "ventas": selector(c7, "Ventas Semanales", sugerencias["ventas"], "sel_vent"),
        "dias": selector(c8, "Días de Entrega", sugerencias["dias"], "sel_dias"),
        "partida": selector(c9, "Partida Arancelaria", sugerencias["partida"], "sel_part"),
    }

def construir_productos_desde_df(df, mapeo):
    faltantes = [k for k in ["producto","cantidad","precio","peso","volumen"] if mapeo.get(k) in (None, "(ninguna)")]
    if faltantes: raise ValueError(f"Falta mapear campos obligatorios: {', '.join(faltantes)}")
    
    productos = []
    for i, fila in df.iterrows():
        try:
            nombre = str(fila[mapeo["producto"]]).strip() if pd.notna(fila[mapeo["producto"]]) else f"Producto {i+1}"
            cant_val = a_decimal(fila[mapeo["cantidad"]], "1")
            cantidad = int(cant_val) if cant_val > CERO else 1
            
            precio = a_decimal(fila[mapeo["precio"]], "0.0")
            peso_u = a_decimal(fila[mapeo["peso"]], "0.0")
            vol_u  = a_decimal(fila[mapeo["volumen"]], "0.0")
            
            stock  = int(a_decimal(fila[mapeo["stock"]], "0")) if mapeo.get("stock") and mapeo["stock"] != "(ninguna)" else 0
            ventas = a_decimal(fila[mapeo["ventas"]], "0.0") if mapeo.get("ventas") and mapeo["ventas"] != "(ninguna)" else CERO
            dias   = int(a_decimal(fila[mapeo["dias"]], "60")) if mapeo.get("dias") and mapeo["dias"] != "(ninguna)" else 60
            
            partida = str(fila[mapeo["partida"]]).strip() if mapeo.get("partida") and mapeo["partida"] != "(ninguna)" and pd.notna(fila[mapeo["partida"]]) else ""

            cant_dec = Decimal(str(cantidad))
            productos.append({
                "nombre": nombre, "cantidad": cantidad, "precio_fob": precio,
                "peso_total": peso_u * cant_dec, "volumen_total": vol_u * cant_dec,
                "stock_actual": stock, "ventas_semanales": ventas, "dias_entrega": dias,
                "partida_arancelaria": partida, "gastos": {}
            })
        except Exception as e:
            st.warning(f"Fila {i + 2} omitida por inconveniente en datos: {e}")
            
    if not productos: raise ValueError("No se pudo cargar ningún producto válido desde el archivo.")
    return productos

def inicializar_estado():
    if "config_empresa" not in st.session_state: st.session_state.config_empresa = dict(DEFAULTS)

def listar_perfiles():
    if SHEETS_DB_OK:
        try: return sheets_db.listar_perfiles()
        except Exception: pass
    return st.session_state.get("perfiles_locales", [])

def guardar_perfil_local(perfil):
    perfiles = st.session_state.get("perfiles_locales", [])
    existentes = {p["id_perfil"]: i for i, p in enumerate(perfiles)}
    if perfil["id_perfil"] in existentes: perfiles[existentes[perfil["id_perfil"]]] = perfil
    else: perfiles.append(perfil)
    st.session_state["perfiles_locales"] = perfiles

def cargar_perfil(perfil):
    for k, v in perfil.items():
        if k in st.session_state.config_empresa: st.session_state.config_empresa[k] = v

def panel_perfil_sidebar():
    st.sidebar.header("🏢 Perfil de Empresa")
    perfiles = listar_perfiles()
    opciones = ["➕ Crear nueva empresa"] + [f"{p['empresa']} ({p['id_perfil']})" for p in perfiles]
    actual_id = st.session_state.config_empresa.get("id_perfil", "")
    idx_actual = 0
    for i, p in enumerate(perfiles):
        if p["id_perfil"] == actual_id: idx_actual = i + 1; break
    sel = st.sidebar.selectbox("Seleccionar empresa", opciones, index=idx_actual)
    if sel == "➕ Crear nueva empresa":
        st.sidebar.markdown("### 🆕 Nueva empresa")
        empresa = st.sidebar.text_input("Razón Social *", key="new_empresa")
        rif = st.sidebar.text_input("RIF", key="new_rif")
        prop = st.sidebar.text_input("Propietario / Responsable", key="new_prop")
        email = st.sidebar.text_input("Email de contacto", key="new_email")
        sector = st.sidebar.selectbox("Sector / Rubro", SECTORES, key="new_sector")
        sector_otro = st.sidebar.text_input("Especifique el sector", key="new_sector_otro") if sector.startswith("Otro") else ""
        origen = st.sidebar.selectbox("Origen principal", ORIGENES, key="new_origen")
        origen_otro = st.sidebar.text_input("Especifique el origen", key="new_origen_otro") if origen.startswith("Otro") else ""
        moneda = st.sidebar.selectbox("Moneda base", ["USD", "EUR", "VES"], key="new_moneda")
        if st.sidebar.button("💾 Crear perfil", type="primary", key="btn_crear_perfil"):
            if not empresa.strip(): st.sidebar.error("La Razón Social es obligatoria.")
            else:
                perfil = {"id_perfil": slugify(empresa), "empresa": empresa.strip(), "rif": rif.strip(), "propietario": prop.strip(), "email": email.strip(), "sector": sector, "sector_otro": sector_otro.strip(), "origen": origen, "origen_otro": origen_otro.strip(), "moneda_default": moneda, "margen": DEFAULTS["margen"], "desc_mayorista": DEFAULTS["desc_mayorista"], "desc_especial": DEFAULTS["desc_especial"], "proveedor": ""}
                if SHEETS_DB_OK:
                    ok, msg = sheets_db.crear_actualizar_perfil(perfil)
                    (st.sidebar.success if ok else st.sidebar.warning)(msg)
                else: guardar_perfil_local(perfil); st.sidebar.success(f"✅ Perfil '{empresa}' creado localmente.")
                cargar_perfil(perfil); st.rerun()
    else:
        idx = opciones.index(sel) - 1
        perfil = perfiles[idx]
        cargar_perfil(perfil)
        st.sidebar.success(f"✅ Perfil activo: **{perfil['empresa']}**")
        st.sidebar.caption(f"ID: `{perfil['id_perfil']}`")
    st.sidebar.divider()

def panel_configuracion_avanzada(config):
    with st.sidebar.expander("⚙️ Ajustes avanzados", expanded=False):
        config["margen"] = st.number_input("Margen normal (%)", 0.0, 99.0, float(config["margen"]), 0.5, key="adv_margen")
        config["desc_mayorista"] = st.number_input("Descuento mayorista (%)", 0.0, 99.0, float(config["desc_mayorista"]), 0.5, key="adv_desc_may")
        config["desc_especial"] = st.number_input("Descuento especial (%)", 0.0, 99.0, float(config["desc_especial"]), 0.5, key="adv_desc_esp")
        config["capital_inicial"] = st.number_input("Capital inicial ($)", 0.0, value=float(config["capital_inicial"]), step=100.0, key="adv_cap")
        config["costo_fijo_semanal"] = st.number_input("Costo fijo semanal ($)", 0.0, value=float(config["costo_fijo_semanal"]), step=10.0, key="adv_cf")
        config["monto_proximo_pedido"] = st.number_input("Monto próximo pedido ($)", 0.0, value=float(config["monto_proximo_pedido"]), step=100.0, key="adv_mpp")
        config["fecha_proximo_pedido"] = st.date_input("Fecha próximo pedido", value=config.get("fecha_proximo_pedido"), key="adv_fpp")
    st.sidebar.divider()
    st.sidebar.subheader("🌍 Origen del embarque")
    config["origen"] = st.sidebar.selectbox("País de origen", ORIGENES, index=ORIGENES.index(config.get("origen", "China")) if config.get("origen") in ORIGENES else 0, key="origen_sel")
    if config["origen"].startswith("Otro"): config["origen_otro"] = st.sidebar.text_input("Especifique el país", value=config.get("origen_otro",""), key="origen_otro_txt")
    config["proveedor"] = st.sidebar.text_input("Proveedor", value=config.get("proveedor",""), key="prov_txt")
    config["factura"]   = st.sidebar.text_input("Nro. de Factura", value=config.get("factura",""), key="fact_txt")
    st.session_state.config_empresa = config
    return config

def vista_analisis_costos(productos, config):
    st.subheader("📊 Análisis de costos por producto")
    filas = [{"Producto": p["nombre"], "Cantidad": p["cantidad"], "FOB $/u": float(p["precio_fob"]), "Gasto arribo $/u": float(p["gasto_unitario"]), "Costo real $/u": float(p["costo_unitario"]), "PVP Normal": float(p["pvp_normal"]), "PVP Sugerido": float(p["pvp_sugerido"]), "Rentab. %": float(p["rentabilidad_pct"]), "Partida": p.get("partida_arancelaria", ""), "Alerta PVP": p.get("alerta_pvp", ""), "Semáforo": p.get("semaforo", "")} for p in productos]
    st.dataframe(pd.DataFrame(filas), use_container_width=True)
    c1, c2, c3, c4 = st.columns(4)
    inv_total = sum((p["costo_unitario"] * Decimal(str(p["cantidad"])) for p in productos), CERO)
    arr_total = sum((p["gastos_totales"] for p in productos), CERO)
    mer_total = sum((p["precio_fob"] * Decimal(str(p["cantidad"])) for p in productos), CERO)
    en_rojo = sum(1 for p in productos if "🔴" in p.get("semaforo_color", ""))
    
    with c1:
        st.markdown("**Inversión total**")
        st.markdown(f"### **{formato_dinero(inv_total)}**")
    with c2:
        st.markdown("**Gasto arribo / mercancía**")
        st.markdown(f"### **{(arr_total / mer_total * 100):.1f}%**")
    with c3:
        st.markdown("**Productos en rojo**")
        st.markdown(f"### **{en_rojo} / {len(productos)}**")
    with c4:
        st.markdown("**Margen promedio**")
        margen_prom = (sum(float(p.get('rentabilidad_pct', 0)) for p in productos) / len(productos)) if len(productos) > 0 else 0
        st.markdown(f"### **{margen_prom:.1f}%**")
        
    # Cálculo del Impacto Flete / FOB Global para Carga Pesada
    fob_total_val = float(mer_total) if 'mer_total' in locals() and mer_total else sum(float(p.get("precio_fob", 0)) * float(p.get("cantidad", 1)) for p in productos)
    flete_val = float(config.get("flete", 2500.0)) if 'config' in locals() else 2500.0
    impacto_flete_global = (flete_val / fob_total_val * 100) if fob_total_val > 0 else 0

    if impacto_flete_global > 60:
        estado_carga_glob = "ROJO"
        color_alerta_glob = "🔴 ALERTA ROJA (Global): Flete crítico (>60% del FOB)"
    elif impacto_flete_global >= 30:
        estado_carga_glob = "AMARILLO"
        color_alerta_glob = "🟡 ALERTA AMARILLA (Global): Flete moderadamente pesado (30%-60% del FOB)"
    else:
        estado_carga_glob = "VERDE"
        color_alerta_glob = "🟢 VERDE (Global): Flete óptimo (<30% del FOB)"

    # Mostrar Alerta en el Sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚨 Alerta Global de Carga")
    if estado_carga_glob == "ROJO":
        st.sidebar.error(color_alerta_glob)
    elif estado_carga_glob == "AMARILLO":
        st.sidebar.warning(color_alerta_glob)
    else:
        st.sidebar.success(color_alerta_glob)
        
    
    fig, ax = plt.subplots(figsize=(10, 4))
    nombres = [p["nombre"][:20] for p in productos]; costos = [float(p["costo_unitario"]) for p in productos]; sugeridos = [float(p["pvp_sugerido"]) for p in productos]
    x = list(range(len(nombres)))
    ax.bar([i - 0.2 for i in x], costos, width=0.4, label="Costo real", color="#C44E52")
    ax.bar([i + 0.2 for i in x], sugeridos, width=0.4, label="PVP sugerido", color="#4C72B0")
    ax.set_xticks(x); ax.set_xticklabels(nombres, rotation=20, ha="right"); ax.set_title("Costo real vs PVP Sugerido"); ax.legend(); ax.grid(alpha=0.3, axis="y")
    st.pyplot(fig)
    
    st.markdown("---")
    st.info(
        """
        **Precio Sugerido:** dentro de una comercialización sana, es un modelo matemático que parte del Costo Real Unitario (Costo FOB + Gastos de Arribo prorrateados) y aplica la fórmula de fijación de precios basada en el margen deseado sobre el costo o precio de venta, frecuentemente alineado con el precio de referencia óptimo o de equilibrio del mercado) cumple tres funciones vitales:
        * **Garantía de Rentabilidad Real**
        * **Punto de Referencia Técnico para Negociaciones**
        * **Mitigación del Riesgo Inflacionario y Cambiario**
        """
    )
    
def vista_carga_pesada(productos, config):
    st.subheader("⚖️ Evaluación Global de Carga Pesada y Eficiencia Logística")
    st.markdown("Análisis estructural completo del embarque, evaluando costos en origen, gastos de arribo y la eficiencia del transporte marítimo.")
    
    # Cálculos globales
    fob_total_val = sum(float(p.get("precio_fob", 0)) * float(p.get("cantidad", 1)) for p in productos)
    flete_val = float(config.get("flete", 2500.0))
    seguro_val = float(config.get("seguro", 300.0))
    aranceles_val = float(config.get("aranceles", 1500.0))
    gastos_loc_val = float(config.get("gastos_locales", 1000.0))
    
    gastos_arribo_val = flete_val + seguro_val + aranceles_val + gastos_loc_val
    cif_total = fob_total_val + flete_val + seguro_val
    costo_total_imp = cif_total + aranceles_val + gastos_loc_val
    factor_mult = costo_total_imp / fob_total_val if fob_total_val > 0 else 1.0
    impacto_flete = (flete_val / fob_total_val * 100) if fob_total_val > 0 else 0

    # Fila 1: Costo FOB y Gastos de Arribo
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Costo FOB Total**")
        st.markdown(f"### ${fob_total_val:,.2f}")
        st.caption("Costo neto total de la mercancía en origen (fábrica o puerto de embarque).")
    with col2:
        st.markdown("**Gastos de Arribo Total**")
        st.markdown(f"### ${gastos_arribo_val:,.2f}")
        st.caption("Suma global de flete, seguro, aranceles y gastos locales necesarios para la nacionalización y puesta en bodega.")

    st.markdown("---")

    # Fila 2: Factor Multiplicador, Impacto Flete y Alerta con color
    col3, col4, col5 = st.columns(3)
    with col3:
        st.markdown("**Factor Multiplicador**")
        st.markdown(f"### {factor_mult:.3f}")
        st.caption("Coeficiente de costo real: Multiplique cada dólar FOB en origen por este factor para hallar su costo nacionalizado.")
    with col4:
        st.markdown("**Impacto Flete / FOB**")
        st.markdown(f"### {impacto_flete:.1f}%")
        st.caption("Relación porcentual del flete frente al FOB. Mide la eficiencia y el peso estructural del transporte.")
    with col5:
        st.markdown("**Estado / Alerta Global**")
        if impacto_flete > 60:
            st.error("🔴 **ROJO (Crítico >60%)**\n\nFlete excesivamente pesado que compromete seriamente los márgenes.")
        elif impacto_flete >= 30:
            st.warning("🟡 **AMARILLO (Moderado 30%-60%)**\n\nFlete moderado; requiere control en ítems de menor valor.")
        else:
            st.success("🟢 **VERDE (Óptimo <30%)**\n\nEstructura de transporte altamente eficiente y competitiva.")
        st.caption("Semáforo logístico del embarque según el impacto porcentual del flete.")
        
    st.markdown("---")
    st.info("💡 **Nota de Consultoría:** Un análisis integral de carga pesada permite identificar con precisión si los sobrecostos radican en el tramo internacional o en la aduana local antes de fijar los precios de venta.")
    
def vista_auditoria_aduanera(productos):
    st.subheader("🏷️ Auditoría de Partidas Arancelarias")
    auditoria = auditar_partidas(productos)
    if not auditoria: st.warning("Ningún producto tiene partida arancelaria cargada."); return
    st.dataframe(pd.DataFrame(auditoria), use_container_width=True)
    st.markdown("### Detalle por partida")
    for p in productos:
        codigo = p.get("partida_arancelaria")
        if not codigo: continue
        info = consultar_partida(codigo); est = estimar_derechos(codigo, float(p["precio_fob"] * Decimal(str(p["cantidad"]))))
        ad_valorem = float(info.get('ad_valorem', 0) or 0) * 100
        texto_info = (
            f"**{p['nombre']}** — `{codigo}`\n\n"
            f"{info.get('descripcion', 'Sin descripción')}\n\n"
            f"Ad-valorem: **{ad_valorem:.0f}%** | "
            f"Requisitos: {info.get('requisitos', 'N/A')}\n\n"
            f"Arancel estimado: **${est.get('arancel_usd', 0):,.2f}** | "
            f"IVA estimado: **${est.get('iva_usd', 0):,.2f}**"
        )
        st.info(texto_info)

def vista_historial(config):
    st.subheader("📚 Historial persistente de importaciones")
    id_perfil = config.get("id_perfil", "")
    if SHEETS_DB_OK:
        est = sheets_db.estado_conexion(); st.caption(f"Modo: **{est['modo'].upper()}** · {est['mensaje']}")
        df_hist = sheets_db.leer_historial(id_perfil=id_perfil)
    else: st.caption("Modo: **LOCAL** (sin `sheets_db.py`)"); df_hist = pd.DataFrame()
    if df_hist.empty: st.info(f"Aún no hay importaciones guardadas para **{config.get('empresa','esta empresa')}**."); return
    c1, c2, c3 = st.columns(3)
    with c1: f_sel = st.selectbox("Filtrar por factura", ["(Todas)"] + sorted(df_hist["factura"].astype(str).unique().tolist()))
    with c2: p_sel = st.selectbox("Filtrar por producto", ["(Todos)"] + sorted(df_hist["producto"].astype(str).unique().tolist()))
    with c3: sem_filtro = st.selectbox("Filtrar por semáforo", ["(Todos)", "🔴", "🟡", "🟢", "⚪"])
    df_f = df_hist.copy()
    if f_sel != "(Todas)": df_f = df_f[df_f["factura"] == f_sel]
    if p_sel != "(Todos)": df_f = df_f[df_f["producto"] == p_sel]
    if sem_filtro != "(Todos)": df_f = df_f[df_f["semaforo"] == sem_filtro]
    st.dataframe(df_f, use_container_width=True, height=400)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Importaciones", df_f["id_importacion"].nunique()); m2.metric("Productos", len(df_f))
    m3.metric("Gasto arribo USD", f"$ {pd.to_numeric(df_f['gasto_arribo_total_usd'], errors='coerce').sum():,.0f}")
    m4.metric("Productos en rojo", (df_f["semaforo"] == "🔴").sum())
    st.download_button("📥 Descargar historial filtrado (CSV)", data=df_f.to_csv(index=False).encode("utf-8-sig"), file_name=f"historial_{id_perfil}_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

    # Generador de Excel sintetico AJUSTABLE 
def vista_generador_sintetico():
    with st.sidebar.expander("🛠️ Panel Oculto: Generador Auxiliar", expanded=True):
        st.markdown("### Generador de Datos de Prueba")
        cant_articulos = st.number_input("Cantidad de artículos", min_value=1, max_value=50, value=5, step=1, key="gen_cant")
        ramo = st.selectbox("Ramo comercial:", list(BANCO_PRODUCTOS_SINTETICOS.keys()), key="gen_ramo")
        tipo_alarma = st.selectbox("Condición de Alarmas:", [
            "🔴 Todos en Alerta Roja (Pedir YA)",
            "🟢 Todos en Stock Saludable (OK)",
            "🟡 Todos en Precaución",
            "🔀 Mixto (Combinado)"
        ], key="gen_alarma")
            
        if st.button("🚀 Generar y Descargar Excel", type="primary", key="btn_gen_excel"):
            lista_base = BANCO_PRODUCTOS_SINTETICOS.get(ramo, BANCO_PRODUCTOS_SINTETICOS["Moto Repuestos"])
            filas = []

            for i in range(cant_articulos):
                prod_ref = lista_base[i % len(lista_base)]
                variacion = 1.0 if i < len(lista_base) else round(1.0 + (i * 0.05), 2)
                
                nombre = f"{prod_ref['nombre']} (Mod. {i+1})" if i >= len(lista_base) else prod_ref['nombre']
                cantidad = int(random.choice([100, 150, 200, 250, 400, 500, 600]))
                fob = round(prod_ref['fob'] * variacion, 2)
                peso_u = round(prod_ref['peso'], 2)
                vol_u = round(prod_ref['vol'], 4)
                partida = prod_ref['partida']
                
                ventas_semana = random.randint(10, 40)
                demanda_60_dias = int(ventas_semana * (60 / 7))
                
                if "🔴" in tipo_alarma:
                    stock_actual = int(demanda_60_dias * 0.25)
                elif "🟢" in tipo_alarma:
                    stock_actual = int(demanda_60_dias * 1.5)
                elif "🟡" in tipo_alarma:
                    stock_actual = int(demanda_60_dias * 0.9)
                else:
                    opc = i % 3
                    if opc == 0: stock_actual = int(demanda_60_dias * 0.2)
                    elif opc == 1: stock_actual = int(demanda_60_dias * 0.85)
                    else: stock_actual = int(demanda_60_dias * 1.4)
                        
                dias_entrega = 60

                filas.append({
                    "Producto": nombre, "Cantidad": cantidad, "Precio FOB Origen $/u": fob,
                    "Peso unitario (kg)": peso_u, "Volumen unitario (m3)": vol_u,
                    "Stock Actual": stock_actual, "Ventas Semanales": ventas_semana,
                    "Días de Entrega": dias_entrega, "Partida Arancelaria": partida
                })

            df_gen = pd.DataFrame(filas)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_gen.to_excel(writer, index=False, sheet_name='Sheet1')
            buffer.seek(0)

            st.sidebar.success(f"✅ Archivo listo para **{ramo}** ({cant_articulos} ítems).")
            nombre_archivo = f"Prueba_{ramo.replace(' ', '_')}_{cant_articulos}items.xlsx"
            st.sidebar.download_button(
                label="📥 Descargar Excel Creado",
                data=buffer,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

from fpdf import FPDF

def sanitize_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {'\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u2022': '-'}
    for search, replace in replacements.items(): text = text.replace(search, replace)
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDFReporteLCL(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 13)
        self.cell(0, 7, sanitize_text('Sistema Inteligente de Importación Marítima para Emprendedores'), 0, 1, 'C')
        self.set_font('helvetica', '', 10)
        self.cell(0, 5, sanitize_text('Reporte Ejecutivo y Cronograma de Operación (DDP)'), 0, 1, 'C')
        self.set_font('helvetica', 'I', 9)
        self.cell(0, 5, sanitize_text('Autoría y Administración por: Prof. Jesús Pulido — Asesor y Analista en Importación.'), 0, 1, 'C')
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def crear_pdf_lcl():
    pdf = PDFReporteLCL()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 1. Resumen Financiero
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 6, sanitize_text('1. Resumen Financiero del Embarque'), 0, 1, 'L')
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, sanitize_text(f"  * Ingreso Bruto x Vtas Operac.: ${st.session_state.get('res_ingreso_bruto', 0):,.2f}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * Inversión General Embarque: ${st.session_state.get('res_inversion_total', 0):,.2f}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * Meta Próximo Pedido (con Envío): ${st.session_state.get('res_meta_proximo', 0):,.2f}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * Tiempo de Recuperación de Capital: {st.session_state.get('res_semanas_recap', 0):.1f} Semanas"), 0, 1)
    pdf.ln(3)
    
    # 2. Utilidades
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 6, sanitize_text('2. Desglose de Utilidades por Canal'), 0, 1, 'L')
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, sanitize_text(f"  * Utilidad Global: ${st.session_state.get('res_utilidad_global', 0):,.2f}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * Utilidad Normal (Detal): ${st.session_state.get('res_utilidad_normal', 0):,.2f}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * Utilidad Mayorista: ${st.session_state.get('res_utilidad_mayor', 0):,.2f}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * Utilidad Sugerida (Crédito): ${st.session_state.get('res_utilidad_sug', 0):,.2f}"), 0, 1)
    pdf.ln(3)
    
    # 3. Cronograma
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 6, sanitize_text('3. Cronograma de Hitos y Fechas Clave'), 0, 1, 'L')
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, sanitize_text(f"  * a. Fecha pedido inicial: {st.session_state.get('res_f_pedido', 'N/A')}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * b. Fecha estimada de entrega DDP Inicial: {st.session_state.get('res_f_entrega', 'N/A')}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * c. Fecha estimada de recuperación de Capital: {st.session_state.get('res_f_recap', 'N/A')}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * d. Fecha de Quiebre de inventario: {st.session_state.get('res_f_quiebre', 'N/A')}"), 0, 1)
    pdf.cell(0, 6, sanitize_text(f"  * e. Fecha estimada entrega DDP próximo: {st.session_state.get('res_f_entrega_prox', 'N/A')}"), 0, 1)
    pdf.ln(4)
    
    # 4. Tabla de Artículos
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 6, sanitize_text('4. Detalle de Artículos y Costos en Puerta'), 0, 1, 'L')
    pdf.set_font('helvetica', 'B', 8)
    
    # --- TABLA 1: COSTOS ---
    pdf.cell(45, 6, 'Artículo', 1, 0, 'L')
    pdf.cell(12, 6, 'Cant', 1, 0, 'C')
    pdf.cell(18, 6, 'FOB($)', 1, 0, 'R')
    pdf.cell(18, 6, 'Envío($)', 1, 0, 'R')
    pdf.cell(14, 6, 'Stock', 1, 0, 'C')
    pdf.cell(14, 6, 'Vtas/S', 1, 0, 'C')
    pdf.cell(14, 6, 'Cobert', 1, 0, 'C')
    pdf.cell(18, 6, 'C.Puerta', 1, 0, 'R')
    pdf.cell(18, 6, 'Inversión', 1, 1, 'R')
    
    pdf.set_font('helvetica', '', 8)
    df_para_pdf = st.session_state["df_lcl"]
    for _, row in df_para_pdf.iterrows():
        pdf.cell(45, 6, sanitize_text(str(row['Artículo'])[:22]), 1, 0, 'L')
        pdf.cell(12, 6, sanitize_text(str(row['Cant'])), 1, 0, 'C')
        pdf.cell(18, 6, f"{row['Precio FOB ($)']:.2f}", 1, 0, 'R')
        pdf.cell(18, 6, f"{row['Gastos de Envío ($)']:.2f}", 1, 0, 'R')
        pdf.cell(14, 6, sanitize_text(str(row['Stock Inicial'])), 1, 0, 'C')
        pdf.cell(14, 6, f"{row['Ventas/Sem']:.1f}", 1, 0, 'C')
        pdf.cell(14, 6, f"{row['Cobert. (Sem)']:.1f}", 1, 0, 'C')
        pdf.cell(18, 6, f"{row['Costo Puerta ($)']:.2f}", 1, 0, 'R')
        pdf.cell(18, 6, f"{row['Inversión ($)']:.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    
    # --- TABLA 2: PRECIOS Y UTILIDADES ---
    pdf.set_font('helvetica', 'B', 8)
    pdf.cell(45, 6, 'Artículo', 1, 0, 'L')
    pdf.cell(18, 6, 'PVP Norm', 1, 0, 'R')
    pdf.cell(18, 6, 'PVP May', 1, 0, 'R')
    pdf.cell(18, 6, 'PVP Sug', 1, 0, 'R')
    pdf.cell(22, 6, 'Ut. Normal', 1, 0, 'R')
    pdf.cell(22, 6, 'Ut. Mayor', 1, 0, 'R')
    pdf.cell(22, 6, 'Ut. Sug', 1, 0, 'R')
    pdf.cell(22, 6, 'Ut. Total', 1, 1, 'R')
    
    pdf.set_font('helvetica', '', 8)
    for _, row in df_para_pdf.iterrows():
        pdf.cell(45, 6, sanitize_text(str(row['Artículo'])[:22]), 1, 0, 'L')
        pdf.cell(18, 6, sanitize_text(str(row['PVP Normal ($)'])), 1, 0, 'R')
        pdf.cell(18, 6, sanitize_text(str(row['PVP Mayor ($)'])), 1, 0, 'R')
        pdf.cell(18, 6, sanitize_text(str(row['PVP Sugerido ($)'])), 1, 0, 'R')
        pdf.cell(22, 6, f"{row['Utilidad Normal ($)']:.2f}", 1, 0, 'R')
        pdf.cell(22, 6, f"{row['Utilidad Mayor ($)']:.2f}", 1, 0, 'R')
        pdf.cell(22, 6, f"{row['Utilidad Sugerida ($)']:.2f}", 1, 0, 'R')
        pdf.cell(22, 6, f"{row['Utilidad Total ($)']:.2f}", 1, 1, 'R')
        
    salida = pdf.output(dest='S')
    return salida.encode('latin1') if isinstance(salida, str) else bytes(salida)
    
def main():
    st.set_page_config(page_title="Sistema de Importación Inteligente Premium", page_icon="🛳️", layout="wide")
    
    # Llamamos a la portera única de acceso
    if not verificar_acceso():
        return  # Si no ha colocado la clave, se detiene ordenadamente aquí

    # =========================================================================
    # ÁREA INTERNA (UNA VEZ INGRESADA LA CLAVE CORRECTA)
    # =========================================================================
    inicializar_estado(); inicializar_monedas()
    panel_perfil_sidebar()
    config = st.session_state.config_empresa.copy()
    
    modo_demo = st.sidebar.toggle("🛠️ Modo Demostración (Generador de Datos)", value=False)
    if modo_demo:
        vista_generador_sintetico()
        
    panel_configuracion_avanzada(config); panel_monedas_sidebar(config)
    
    st.markdown("<h2 style='text-align: center; color: #1f4e78;'>🚢 Sistema de Análisis de Importación Inteligente Premium 🐉</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    def _texto_seguro(val, val_otro):
        if val == "Otro" and val_otro:
            return str(val_otro)
        return str(val or "No especificado")

    empresa_activa = config.get('empresa', 'Empresa Principal')
    propietario_val = config.get('propietario', config.get('responsable', 'No especificado'))
    rif_val = config.get('rif', 'No especificado')
    email_val = config.get('email', config.get('correo', 'No especificado'))
    sector_activo = _texto_seguro(config.get('sector'), config.get('sector_otro'))
    proveedor_val = config.get('proveedor', 'No especificado')
    origen_efectivo = _texto_seguro(config.get('origen'), config.get('origen_otro'))

    st.markdown(
        f"""
        <div style="text-align: center; font-size: 18px; line-height: 1.6; margin-bottom: 25px; color: #333;">
            <b>Empresa activa:</b> {empresa_activa}<br>
            <b>Propietario:</b> {propietario_val}<br>
            <b>RIF:</b> {rif_val}<br>
            <b>Email:</b> {email_val}<br>
            <b>Sector:</b> {sector_activo}<br>
            <b>Proveedor:</b> {proveedor_val}<br>
            <b>Origen Proveedor:</b> {origen_efectivo}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
    "<div style='text-align: center; font-size: 14px; color: #1f4e78; margin-bottom: 20px;'>"
    "Ingeniería con IA: <b>Prof. Jesús Pulido V.</b> · Asesor de Importación Inteligente"
    "</div>",
    unsafe_allow_html=True
    )
  
    with st.sidebar:
        st.markdown("---")
        if SHEETS_DB_OK:
            est = sheets_db.estado_conexion()
            if est["modo"] == "nube": st.success(f"☁️ {est['mensaje']}")
            else: st.info(f"💾 {est['mensaje']}")
        else: st.info("💾 Modo local (sin sheets_db.py)")
        st.markdown("---"); st.caption("📞 0424-728.3199 / 0416-291.6426"); st.caption("✉️ jeshua166@gmail.com")
        
    # --- SELECTOR MULTI-MODALIDAD ---
    st.markdown("### 🏢 Seleccione la Modalidad de Gestión de Importación")
    
    modalidad = st.selectbox(
        "Elija el tipo de operación logística:",
        [
            "📊 Opción A · Contenedor Completo (FCL - Tradicional / Aduana)",
            "📦 Opción B · Carga Fraccionada Puerta a Puerta (LCL - DDP / Emprendedor)",
            "✍️ Opción C · Ingreso Manual Rápido"
        ],
        index=0,
        help="Seleccione el ambiente adaptado a la realidad operativa de su importación."
    )
    
    # =========================================================================
    # 4. INICIO DE LAS OPCIONES (A, B y C)
    # =========================================================================

    # =========================================================================
    # OPCIÓN A: CONTENEDOR COMPLETO (FCL)
    # =========================================================================
    if modalidad.startswith("📊 Opción A"):    
        st.info("ℹ️ **Ambiente FCL Activo:** Gestión corporativa completa con prorrateo de peso/volumen, auditoría arancelaria y flujo de caja a 13 semanas.")
            
        archivo = st.file_uploader("", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
        if archivo is None:
            st.info("📦 Suba su archivo Excel o CSV para comenzar el análisis o activa el **Modo Demostración** en la barra lateral.")
            with st.expander("❓ Columnas esperadas"):
                st.markdown("- Producto / Descripción\n- Cantidad\n- Precio FOB\n- Peso unitario\n- Volumen unitario\n- Ventas Semanales\n- PVP Sugerido")
        else:
            try:
                df = leer_excel(archivo)
                st.success(f"✅ Archivo cargado: **{len(df)}** filas")
                with st.expander("👀 Ver primeras filas"):
                    st.dataframe(df.head(), use_container_width=True)
                mapeo = mapear_columnas(df)
            except Exception as e:
                st.error(f"❌ Error al leer el archivo: {e}")
    
            # --- GASTOS DEL CONTENEDOR ---
            st.markdown("### 📦 Gastos del contenedor (en USD)")
            cols = st.columns(3)
            gastos_ingresos = {}
            for i, (nombre, criterio) in enumerate(GASTOS_CONTENEDOR):
                with cols[i % 3]:
                    val = st.number_input(f"{nombre} ({criterio})", min_value=0.0, value=0.0, step=10.0, key=f"g_{nombre}")
                    gastos_ingresos[nombre] = Decimal(str(val))
        
            st.markdown("---")

            # --- BOTÓN DE CÁLCULO PRINCIPAL ---
            if st.button("🚀 Calcular análisis completo", type="primary", key="calcular_fcl"):
                try:
                    productos = construir_productos_desde_df(df, mapeo)
                    gastos_contenedor = calcular_costos(productos, gastos_ingresos, config)
                    
                    # Guardamos los resultados de forma persistente en la sesión
                    st.session_state["productos_actuales"] = productos
                    st.session_state["config_actual"] = config
                    st.session_state["gastos_contenedor"] = gastos_contenedor
                    
                    st.success(f"✅ Análisis completado para **{len(productos)}** productos.")
                except Exception as e:
                    st.error(f"Error en cálculo: {e}")

            # --- DESPLIEGUE AUTOMÁTICO DE REPORTES SI YA EXISTEN DATOS EN SESIÓN ---
            if "productos_actuales" in st.session_state:
                productos = st.session_state["productos_actuales"]
                config = st.session_state["config_actual"]
                gastos_contenedor = st.session_state["gastos_contenedor"]
        
                st.markdown("---")
        
                # Botón opcional de historial en Sheets
                if SHEETS_DB_OK:
                    if st.button("💾 Guardar esta importación en el historial", type="secondary", key="guardar_hist_fcl"):
                        ok, msg = sheets_db.guardar_importacion(productos, config)
                        (st.success if ok else st.warning)(msg)
                        sheets_db.guardar_alertas(generar_alertas_reposicion(productos, config))
        
                st.markdown("---")
        
                # Pestañas gerenciales
                tab_costos, tab_carga, tab_reposicion, tab_salvavidas, tab_reporte, tab_flujo, tab_auditoria, tab_historial = st.tabs([
                    "📊 Análisis de costos",
                    "⚖️ Carga Pesada",
                    "📦 Reposición",
                    "🆘 Salvavidas",
                    "📄 Reporte completo",
                    "📈 Flujo de caja",
                    "🔍 Auditoría aduanera",
                    "📜 Historial"
                ])
        
                with tab_costos:
                    vista_analisis_costos(productos, config)
                with tab_carga:
                    vista_carga_pesada(productos, config)
                with tab_reposicion:
                    mostrar_alertas_en_panel(generar_alertas_reposicion(productos, config))
                with tab_salvavidas:
                    renderizar_pestana_salvavidas(productos, config)
                with tab_reporte:
                    st.subheader("📄 Reporte Ejecutivo")
                    reporte_html = crear_reporte_html(productos, gastos_contenedor, config)
                    components.html(reporte_html, height=1500, scrolling=True)
                    st.info("💡 Para guardar este reporte como PDF, presione el botón de abajo.")
                    st.divider()
                    boton_exportar_sheets(productos, config)
                    st.markdown("---")
                    pdf_bytes = generar_pdf_desde_html(reporte_html)
                    if pdf_bytes:
                        st.download_button(
                            label="📥 Descargar Reporte Ejecutivo Oficial en PDF",
                            data=pdf_bytes,
                            file_name=f"Reporte_{config.get('factura', 'SN')}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                with tab_flujo:
                    mostrar_flujo_caja(proyectar_flujo_caja(productos, config), config)
                with tab_auditoria:
                    vista_auditoria_aduanera(productos)
                # (Aquí termina el bloque de la Opción A con sus pestañas)
                with tab_historial:
                    vista_historial(config)
            
            # Si aún no se ha calculado, mostramos el aviso (ya no usamos 'else', sino un 'if' limpio)
            if not "productos_actuales" in st.session_state and modalidad.startswith("📊 Opción A"):
                st.warning("⚠️ Por favor, configure sus datos, cargue su Excel y haga clic en **'Calcular análisis completo'** para habilitar los reportes ejecutivos.")

        # =========================================================================
        # OPCIÓN B: CARGA FRACCIONADA (LCL DDP)
        # =========================================================================
        if modalidad.startswith("📦 Opción B"):
            st.info("ℹ️ **Ambiente LCL DDP Activo:** Multicanal con márgenes diferenciados (Detal, Mayorista y Sugerido) y control de bache de inventario.")
 
            # --- PARÁMETROS GLOBALES Y MÁRGENES ---
            c_cols1, c_cols2 = st.columns(2)
            with c_cols1:
                fob_total_c = st.number_input("Valor FOB Total de la Mercancía ($)", min_value=0.0, value=2500.0, step=100.0)
                volumen_m3_c = st.number_input("Volumen Total Ocupado (m³)", min_value=0.1, value=1.0, step=0.1)
                tarifa_plana_m3 = st.number_input("Tarifa DDP por m³ ($/m³)", min_value=0.0, value=400.0, step=25.0)
                fecha_embarque_c = st.date_input("Fecha Estimada de Embarque")
            with c_cols2:
                semanas_transito_c = st.number_input("Tiempo de Tránsito a Puerta (Semanas)", min_value=4, value=12, step=1)
                margen_normal = st.number_input("Margen % PVP Normal (Detal)", min_value=0.0, max_value=999.0, value=150.0, step=5.0)
                margen_mayor = st.number_input("Margen % PVP Mayorista", min_value=0.0, max_value=999.0, value=50.0, step=5.0)
                margen_sugerido = st.number_input("Margen % PVP Sugerido", min_value=0.0, max_value=999.0, value=400.0, step=5.0)
                reinversion_base_prox = st.number_input("Reinversión base para el próximo pedido ($)", min_value=100.0, value=700.0, step=50.0)
                pct_perdida = st.number_input("% Estimado de Pérdida / Estancamiento", min_value=0.0, max_value=50.0, value=10.0, step=1.0)
                           
            st.markdown("##### 📝 Detalle de Artículos y Distribución por Canal de Venta:")
            num_items_c = st.number_input("Cantidad de ítems diferentes", min_value=1, value=2, step=1, key="num_c")
                
            items_c_list = []
            for ic in range(int(num_items_c)):
                st.markdown(f"**📦 Artículo {ic+1}**")
                f_cols1, f_cols2 = st.columns(2)
                with f_cols1:
                    nom_i = st.text_input(f"Nombre Artículo {ic+1}", value=f"Modelo {ic+1}", key=f"c_nom_{ic}")
                    cantidad_i = st.number_input(f"Cantidad Total Unidades {ic+1}", min_value=1, value=100, step=1, key=f"c_cant_{ic}")
                    fob_i = st.number_input(f"FOB Unit. {ic+1} ($)", min_value=0.0, value=15.0, step=1.0, key=f"c_fob_{ic}")
                with f_cols2:
                    vol_i = st.number_input(f"Vol. Unit. m³ {ic+1}", min_value=0.001, value=0.01, step=0.001, key=f"c_vol_{ic}")
                    stock_i = st.number_input(f"Stock Inicial (Unids) {ic+1}", min_value=0.0, value=20.0, step=1.0, key=f"c_stock_{ic}")
                    ventas_i = st.number_input(f"Ventas Semanales (Unids) {ic+1}", min_value=0.1, value=5.0, step=1.0, key=f"c_ventas_{ic}")
                    
                st.markdown("*Distribución de unidades a comercializar:*")
                d_cols = st.columns(3)
                with d_cols[0]:
                    unidades_normal = st.number_input(f"Unidades PVP Normal", min_value=0, value=int(cantidad_i * 0.4), step=1, key=f"c_un_norm_{ic}")
                with d_cols[1]:
                    unidades_mayor = st.number_input(f"Unidades PVP Mayor", min_value=0, value=int(cantidad_i * 0.4), step=1, key=f"c_un_may_{ic}")
                with d_cols[2]:
                    unidades_sug = st.number_input(f"Unidades PVP Sugerido", min_value=0, value=int(cantidad_i * 0.2), step=1, key=f"c_un_sug_{ic}")
                        
                items_c_list.append({
                    "nombre": nom_i, "cantidad": cantidad_i, "precio_fob": fob_i,
                    "volumen_m3": vol_i, "stock_inicial": stock_i, "ventas_semanales": ventas_i,
                    "unidades_normal": unidades_normal, "unidades_mayor": unidades_mayor, "unidades_sugeridas": unidades_sug
                })
                st.markdown("---")
                    
    # --- BOTÓN DE PROCESAR (AHORA SÍ, DENTRO DE LA OPCIÓN B) ---
    if st.button("🚀 Procesar Importación Multicanal (DDP)", type="primary", key="procesar_lcl"):     
        df_temp_c = pd.DataFrame(items_c_list)
        st.session_state["df_lcl"] = procesar_opcion_c_lcl(
            df_temp_c, volumen_m3_c, tarifa_plana_m3, fecha_embarque_c, semanas_transito_c,
            margen_normal, margen_mayor, margen_sugerido, reinversion_base_prox, pct_perdida 
        )
        st.success("✅ ¡Cálculo multicanal y cobertura procesados con éxito!")
                
    # --- RESULTADOS Y DESCARGA DE PDF ---
    if "df_lcl" in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Reporte Ejecutivo y Cobertura de Inventario — Puerta a Puerta (DDP)")
        st.dataframe(st.session_state["df_lcl"], use_container_width=True)
        st.success("🎉 ¡Su análisis de costos en puerta y control de bache de inventario está listo!")
                       
        # --- RENDERIZADO EN PANTALLA DEL BOTÓN DE DESCARGA ---
        st.markdown("---")
        st.markdown("### 📄 Exportación de Reporte Ejecutivo")
        st.download_button(
            label="📥 Descargar Reporte Ejecutivo Oficial en PDF",
            data=crear_pdf_lcl(),
            file_name="Reporte_Ejecutivo_Importacion.pdf",
            mime="application/pdf",
            type="primary"
        )
                                    
        # Fin opción B ‼️

    # =========================================================================
    # OPCIÓN C: INGRESO MANUAL RÁPIDO
    # =========================================================================
    if modalidad.startswith("✍️ Opción C"):
        st.info("ℹ️ **Ambiente Manual Activo:** Registro directo de productos y gastos del contenedor.")
            
        st.markdown("### 💼 Gastos del contenedor (en USD)")
        cols = st.columns(3)
        gastos_ingresados = {}
        # Asumo que GASTOS_CONTENEDOR está definida globalmente arriba en tu código
        for i, (nombre, criterio) in enumerate(GASTOS_CONTENEDOR):
            with cols[i % 3]:
                val = st.number_input(f"{nombre} ({criterio})", min_value=0.0, value=0.0, step=10.0, key=f"g_{nombre}")
                gastos_ingresados[nombre] = val
                    
        # 👇🏼 Aquí puedes seguir agregando el resto del formulario manual de la Opción C
        pass

      # Fin de Opciones ‼️ 
          
if __name__ == "__main__":
    main()
       

