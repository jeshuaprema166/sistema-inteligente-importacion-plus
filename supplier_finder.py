"""
Buscador de proveedores alternativos para cubrir fallas de inventario.
Devuelve candidatos con localidad, teléfono (o aviso si no está disponible) y fuente.
"""
import json
import re
from dataclasses import dataclass, asdict
from typing import Optional

from tavily import TavilyClient
from openai import OpenAI

PHONE_RE = re.compile(r"(?:\+?58[\s.\-]?)?(?:0)?[24]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{4}")


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
    base = producto.strip()
    qs = [
        f'distribuidor mayorista ferretería "{base}" Venezuela teléfono',
        f'"{base}" al mayor Venezuela proveedor distribución',
        f'ferretería industrial mayorista Venezuela "{base}"',
    ]
    if ciudad:
        qs.append(f'distribuidor ferretero {ciudad} "{base}" al mayor')
    return qs


def search_all(queries: list[str], api_key: str, per_query: int = 5) -> list[dict]:
    client = TavilyClient(api_key=api_key)
    seen, hits = set(), []
    for q in queries:
        try:
            res = client.search(query=q, max_results=per_query, search_depth="advanced", include_raw_content=False)
            for r in res.get("results", []):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    hits.append({"url": url, "title": r.get("title", ""), "content": r.get("content", "")})
        except Exception as e:
            print(f"[search] fallo en '{q}': {e}")
    return hits


LLM_PROMPT = """Extrae proveedores mayoristas REALES del texto. Reglas estrictas:
- Solo empresas mencionadas explícitamente en el texto.
- NO inventes datos. Si un campo no aparece, déjalo vacío ("").
- 'telefonos': copia literalmente los números tal como aparecen.
- 'senales_mayorista': true si el texto dice "al mayor", "mayorista", "distribuidor", "distribución".
- 'menciona_producto': true si el texto menciona el producto consultado o su categoría.
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
                    {"role": "user", "content": f"Producto buscado: {producto}\n\n{bloque}"},
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
            "senales_mayorista": any(k in texto for k in ("al mayor", "mayorista", "distribuid")),
            "menciona_producto": any(t in texto for t in tokens),
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
        if not tokens or any(t in nombre.lower() for t in tokens):
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
