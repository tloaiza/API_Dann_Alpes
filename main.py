from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
 
app = FastAPI()
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
 
client = MongoClient(os.environ["MONGO_URI"])
db = client["ISIS2304E11202610"]
 
 
@app.get("/")
def inicio():
    return {"estado": "API funcionando correctamente"}
 
 
# RF1 -- Crear reseña
@app.post('/resenas')
def crear_resena(datos: dict = Body(...)):
    existente = db["resenas"].find_one({"reserva_id": datos.get("reserva_id")})
    if existente:
        return {"mensaje": "Ya existe una reseña para esta reserva"}
 
    datos['fecha_creacion']  = datetime.now()
    datos['estado']          = "publicada"
    datos['votos_util']      = 0
    datos['votantes']        = []
    datos['respuesta_admin'] = None
    datos['destacada']       = False
 
    resultado = db["resenas"].insert_one(datos)
    return {"mensaje": "Reseña creada exitosamente", "id": str(resultado.inserted_id)}
 
 
# RF2 -- Editar reseña (cliente edita texto y calificación)
@app.put('/resenas/{resena_id}')
def editar_resena(resena_id: str, datos: dict = Body(...)):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {
            "texto":        datos.get("texto"),
            "calificacion": datos.get("calificacion")
        }}
    )
    return {"mensaje": "Reseña editada exitosamente"}
 
 
# RF3 -- Eliminar reseña (cliente)
@app.delete('/resenas/{resena_id}')
def eliminar_resena_cliente(resena_id: str):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"estado": "eliminada"}}
    )
    return {"mensaje": "Reseña eliminada exitosamente"}
 
 
# RF4 -- Consultar reseñas de un hotel
@app.get('/hoteles/{hotel_id}/resenas')
def get_resenas_hotel(hotel_id: int, orden: str = "fecha", pagina: int = 1, por_pagina: int = 10):
    campo_orden = "fecha_creacion" if orden == "fecha" else "votos_util"
    skip = (pagina - 1) * por_pagina
 
    destacadas = list(db["resenas"].find(
        {"hotel_id": hotel_id, "estado": "publicada", "destacada": True},
        {"_id": 1, "calificacion": 1, "texto": 1, "fecha_creacion": 1,
         "votos_util": 1, "respuesta_admin": 1, "destacada": 1, "usuario_id": 1}
    ))
 
    normales = list(db["resenas"].find(
        {"hotel_id": hotel_id, "estado": "publicada", "destacada": False},
        {"_id": 1, "calificacion": 1, "texto": 1, "fecha_creacion": 1,
         "votos_util": 1, "respuesta_admin": 1, "destacada": 1, "usuario_id": 1}
    ).sort(campo_orden, -1).skip(skip).limit(por_pagina))
 
    for i in destacadas + normales:
        i["_id"] = str(i["_id"])
        if i.get("fecha_creacion"):
            i["fecha_creacion"] = i["fecha_creacion"].isoformat()
        if i.get("respuesta_admin") and i["respuesta_admin"].get("fecha"):
            i["respuesta_admin"]["fecha"] = i["respuesta_admin"]["fecha"].isoformat()
 
    return {"resenas": destacadas + normales}
 
 
# RF5 -- Marcar reseña como útil
@app.post('/resenas/{resena_id}/voto')
def votar_resena(resena_id: str, datos: dict = Body(...)):
    usuario_id = datos.get("usuario_id")
 
    resena = db["resenas"].find_one({"_id": ObjectId(resena_id)})
    if not resena:
        return {"mensaje": "Reseña no encontrada"}
 
    if usuario_id in resena.get("votantes", []):
        return {"mensaje": "El usuario ya votó por esta reseña"}
 
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {
            "$inc":  {"votos_util": 1},
            "$push": {"votantes": usuario_id}
        }
    )
    return {"mensaje": "Voto registrado exitosamente"}
 
 
# RF6 -- Consultar historial de reseñas propias
@app.get('/usuarios/{usuario_id}/resenas')
def get_resenas_usuario(usuario_id: int, orden: str = "fecha"):
    campo_orden = "fecha_creacion" if orden == "fecha" else "hotel_id"
    resenas = list(db["resenas"].find(
        {"usuario_id": usuario_id},
        {"_id": 1, "hotel_id": 1, "calificacion": 1, "texto": 1,
         "fecha_creacion": 1, "estado": 1, "votos_util": 1, "respuesta_admin": 1}
    ).sort(campo_orden, -1))
 
    for i in resenas:
        i["_id"] = str(i["_id"])
        if i.get("fecha_creacion"):
            i["fecha_creacion"] = i["fecha_creacion"].isoformat()
 
    return {"resenas": resenas}
 
 
# RF7 -- Responder reseña (administrador)
@app.put('/resenas/{resena_id}/respuesta')
def responder_resena(resena_id: str, datos: dict = Body(...)):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {
            "respuesta_admin": {
                "texto": datos.get("texto"),
                "fecha": datetime.now()
            }
        }}
    )
    return {"mensaje": "Respuesta registrada exitosamente"}
 
 
# RF8 -- Eliminar reseña (administrador)
@app.delete('/resenas/{resena_id}/admin')
def eliminar_resena_admin(resena_id: str):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"estado": "eliminada"}}
    )
    return {"mensaje": "Reseña eliminada por administrador"}
 
 
# RF9 -- Destacar reseña (administrador, solo una por hotel)
@app.put('/resenas/{resena_id}/destacar')
def destacar_resena(resena_id: str):
    resena = db["resenas"].find_one({"_id": ObjectId(resena_id)})
    if not resena:
        return {"mensaje": "Reseña no encontrada"}
 
    db["resenas"].update_many(
        {"hotel_id": resena["hotel_id"], "destacada": True},
        {"$set": {"destacada": False}}
    )
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"destacada": True}}
    )
    return {"mensaje": "Reseña destacada exitosamente"}
 