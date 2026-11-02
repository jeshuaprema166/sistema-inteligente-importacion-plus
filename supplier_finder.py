"""
Buscador de proveedores alternativos con búsqueda inteligente sesgada por rubro.
Utiliza las ramas comerciales predefinidas de la plataforma para mayor precisión.
"""
import json
import re
from dataclasses import dataclass, asdict
from typing import Optional
import streamlit as st  # Importamos Streamlit para acceder a la sesión

from tavily import TavilyClient
from openai import OpenAI

PHONE_RE = re.compile(r"(?:\+?58[\s.\-]?)?(?:0)?[24]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{4}")

# Mapeo de rubros de la interfaz a términos de búsqueda clave
RUBRO_QUERIES = {
    "Ferretería / Herramientas": ["distribuidor ferretero mayorista", "ferretería industrial Venezuela", "mayorista herramientas construcción"],
    "Repuestos para motos": ["repuestos motos al mayor", "distribuidor partes motocicletas Venezuela", "importador repuestos moto"],
    "Repuestos para automóviles": ["repuestos carros al mayor Venezuela", "distribuidor autopartes mayoreo", "importador repuestos automotrices"],
    "Cauchos y neumáticos": ["mayorista cauchos Venezuela", "distribuidor neumáticos al mayor", "importador cauchos"],
    "Construcción / Materiales": ["distribuidor materiales construcción mayorista", "mayorista ferretería pesada Venezuela", "materiales obra al mayor"],
    "Agro / Insumos": ["distribuidor agropecuario mayorista", "insumos agrícolas al mayor Venezuela", "mayorista agroquímicos"],
    "Tecnología / Electrónica": ["mayorista tecnología Venezuela", "distribuidor electrónica al mayor", "importador equipos electrónicos"],
    "Textil / Calzado": ["textil al mayor Venezuela", "distribuidor telas mayorista", "fábrica calzado mayorista"],
    "Salud / Farmacia": ["distribuidor farmacéutico mayorista Venezuela", "droguería Venezuela", "mayorista equipos médicos"],
    "Otro (especificar)": ["distribuidor mayorista Venezuela", "proveedor al mayor comercial", "mayorista"] # Respaldo genérico inteligente
}

def normalize_phone(raw: str) -> Optional[str]:
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("58") and len(d) == 12:
        d = "0" + d[2:]
    if len(d) == 10 and d[0] == "0" and d[1] in "24":
        return f"{d[:4]}-{d[4:]}"
    return None


def phone_appears_in_source(phone: str, content: str) -> bool:
    target = re.sub(r"\D", "", phone)
    return target in re.sub(r"\D", "", content or "")


def wa_link(phone: str) -> str:
    d = re.sub(r"\D", "", phone)
    if d.startswith("0"):
        d = "58" + d[1:]
    return f"https://wa.me/{d}"


@dataclass
class Candidate:
    nombre: str
    localidad: str = ""
    direccion: str = ""
    telefono: str = ""
    senales_mayorista: bool = False
    menciona_producto: bool = False
    fuente: str = ""
    confianza: str = "candidato"
    score: int = 0


def build_queries(producto: str, ciudad: Optional[str] = None) -> list[str]:
    """
    Construye consultas sesgadas inteligentemente por el rubro de la empresa
    y el nombre específico del producto.
    """
    base = producto.strip()
    
    # Obtenemos el rubro de la empresa activa desde la sesión
    rubro_empresa = "Otro (especificar)" # Valor por defecto
    if "config_empresa" in st.session_state:
        rubro_empresa = st.session_state["config_empresa"].get("rubro", "Otro (especificar)")
    elif "temp_config" in st.session_state: # Para empresas nuevas en proceso de creación
        rubro_empresa = st.session_state["temp_config"].get("rubro", "Otro (especificar)")
        
    # Obtenemos los términos de búsqueda clave para ese rubro específico
    terminos_rubro = RUBRO_QUERIES.get(rubro_empresa, RUBRO_QUERIES["Otro (especificar)"])

    # Construimos las consultas combinando Tavily + LLM
    # Priorizamos encontrar el producto ESPECÍFICO dentro de ese rubro ESPECÍFICO
    qs = [
        f'distribuidor mayorista "{base}" Venezuela rubro {rubro_empresa}',
        f'proveedor al mayor "{base}" Venezuela sector {rubro_empresa}',
        f'comercializadora de {base} Venezuela',
        f'{terminos_rubro[0]} Venezuela {base}',
        f'{terminos_rubro[1]} Venezuela',
    ]
    if ciudad:
        qs.insert(0, f'distribuidor mayorista {ciudad} "{base}"')
        qs.append(f'proveedor al mayor {ciudad} {terminos_rubro[2]}')
    
    return list(set(qs)) # Eliminamos duplicados


def search_all(queries: list[str], api_key: str, per_query: int = 4) -> list[dict]:
    client = TavilyClient(api_key=api_key)
    seen, hits = set(), []
    for q in queries:
        try:
            print(f"Ejecutando búsqueda: {q}") # Para depuración
            res = client.search(query=q, max_results=per_query, search_depth="advanced", include_raw_content=False)
            for r in res.get("results", []):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    hits.append({"url": url, "title": r.get("title", ""), "content": r.get("content", "")})
        except Exception as e:
            print(f"[search] fallo en '{q}': {e}")
    return hits


LLM_PROMPT = """Extrae proveedores mayoristas, distribuidores o comercializadoras REALES del texto. Reglas estrictas:
- Solo empresas mencionadas explícitamente en el texto.
- NO inventes datos. Si un campo no aparece, déjalo vacío ("").
- 'telefonos': copia literalmente los números tal como aparecen.
- 'senales_mayorista': true si el texto dice "al mayor", "mayorista", "distribuidor", "distribución", "comercializadora", "mayor".
- 'menciona_producto': true si el texto menciona el producto o categoría afín.
Devuelve SOLO JSON: {"proveedores":[{"nombre":"","localidad":"","direccion":"","telefonos":[],"senales_mayorista":false,"menciona_producto":false,"url_fuente":""}]}"""


def extract_llm(hits: list[dict], producto: str, api_key: str, chunk: int = 6) -> list[dict]:
    client = OpenAI(api_key=api_key)
    out = []
    for i in range(0, len(hits), chunk):
        bloque = "\n\n---\n\n".join(
            f"URL: {h['url']}\nTITULO: {h['title']}\nTEXTO: {h['content'][:1800]}"
            for h in hits[i:i + chunk]
        )
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": LLM_PROMPT},
                    {"role": "user", "content": f"Ítem buscado: {producto}\n\n{bloque}"},
                ],
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            out.extend(data.get("proveedores", []))
        except Exception as e:
            print(f"[llm] fallo en chunk {i}: {e}")
    return out


def extract_heuristic(hits: list[dict], producto: str) -> list[dict]:
    out = []
    tokens = [t.lower() for t in producto.split() if len(t) > 3]
    for h in hits:
        phones = list({normalize_phone(p) for p in PHONE_RE.findall(h["content"] + " " + h["title"]) if normalize_phone(p)})
        texto = (h["content"] + " " + h["title"]).lower()
        out.append({
            "nombre": h["title"].split("|")[0].split("-")[0].strip()[:80],
            "localidad": "", "direccion": "",
            "telefonos": phones,
            "senales_mayorista": any(k in texto for k in ("al mayor", "mayorista", "distribuid", "mayor", "comercializadora")),
            "menciona_producto": any(t in texto for t in tokens) or len(tokens) == 0,
            "url_fuente": h["url"],
        })
    return out


def consolidate(raw: list[dict], hits: list[dict], producto: str, ciudad: Optional[str]) -> list[Candidate]:
    contenido_total = " ".join(h["content"] for h in hits)
    tokens = [t.lower() for t in producto.split() if len(t) > 3]
    out: list[Candidate] = []

    for r in raw:
        nombre = (r.get("nombre") or "").strip()
        if not nombre:
            continue

        tel_valido = ""
        for t in r.get("telefonos", []) or []:
            n = normalize_phone(t)
            if n and phone_appears_in_source(n, contenido_total):
                tel_valido = n
                break

        localidad = (r.get("localidad") or "").strip()
        señales = bool(r.get("senales_mayorista"))
        menciona = bool(r.get("menciona_producto"))
        direccion = (r.get("direccion") or "").strip()
        fuente = r.get("url_fuente") or (hits[0]["url"] if hits else "")

        score = 0
        score += 3 if tel_valido else 0
        score += 2 if señales else 0
        score += 2 if menciona else 0
        score += 1 if direccion else 0
        score += 1 if localidad else 0
        if ciudad and ciudad.lower() in localidad.lower():
            score += 1

        out.append(Candidate(
            nombre=nombre, localidad=localidad, direccion=direccion,
            telefono=tel_valido, senales_mayorista=señales,
            menciona_producto=menciona, fuente=fuente, score=score,
        ))

    vistos, unicos = set(), []
    for c in sorted(out, key=lambda x: x.score, reverse=True):
        key = re.sub(r"[^a-z0-9]", "", c.nombre.lower())[:25] or c.telefono or c.fuente
        if key in vistos:
            continue
        vistos.add(key)
        unicos.append(c)
    return unicos


def find_suppliers(producto: str, cantidad: int | None, ciudad: str | None,
                   tavily_key: str, openai_key: str | None = None,
                   top_n: int = 6, _tavily=None, _openai=None) -> list[dict]:
    queries = build_queries(producto, ciudad)
    hits = search_all(queries, tavily_key)
    
    if not hits:
        return []

    if openai_key:
        raw = extract_llm(hits, producto, openai_key)
        if not raw:
            raw = extract_heuristic(hits, producto)
    else:
        raw = extract_heuristic(hits, producto)

    mejores = consolidate(raw, hits, producto, ciudad)[:top_n]
    
    if not mejores and hits:
        for h in hits[:top_n]:
            mejores.append(Candidate(
                nombre=h["title"].split("|")[0].split("-")[0].strip()[:80],
                localidad="", direccion="", telefono="",
                senales_mayorista=True, menciona_producto=True,
                fuente=h["url"], score=1
            ))
            
    return [asdict(c) for c in mejores]
        
