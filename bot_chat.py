from config import token_telegram, palabras_prohibidas
from datetime import datetime, timedelta
import re
import os
from pprint import pprint
from shutil import move
import telebot #para manejar la API de telegram

bot = telebot.TeleBot(token_telegram)

# carpetas
Dic_avisos = {
    "avisos" : "avisos",
    "baneados" : "baneados"
}

#recorremos el diccionario
for clave, valor in Dic_avisos.items():
    if not os.path.isdir(valor):
        os.mkdir(valor)

max_avisos = 3

@bot.message_handler(content_types=["new_chat_members"]) # conseguimos que solo de bienvenida a nuevos usuarios
# Dar mensaje de bienvenida a los nuevos usuarios
def bienvenida(m):
    for x in m.new_chat_members:
        bot.send_message(m.chat.id, f'Bienvenido <b>{x.first_name}</b>', parse_mode="HTML")

# responde al comando -> /unban
@bot.message_handler(commands = ["unban"])
def cmd_unban(m):
    # info -> "/unban" muestra la lista de los usuarios baneados
    # info -> "/unban <indice>" desbanea al usuario desde el indice - ejm: 2 Carlos -- /unban 2
    cid = m.chat.id
    #comprobamos si el usuario es el creador del grupo o administrador
    info_miembro = bot.get_chat_member(cid, m.from_user.id)
    pprint(info_miembro.__dict__)
    if not info_miembro.status in ["creator", "administrator"]:
        #finalizamos la funcion
        return
    archivos = os.listdir(Dic_avisos["baneados"])
    if not archivos:
        bot.send_message(cid, 'No hay ningun usuario baneado')
        return
    else:
        #creamos una lista de tuplas
        nombres = []
        for archivo in archivos:
            with open(f'{Dic_avisos["baneados"]}/{archivo}', "r", encoding="utf-8") as f:
                nombre = f.read().split("\n")[1]
                nombres.append((nombre,archivo))
        param = m.text.split()
        if len(param) == 1:
            texto = ""
            n = 0
            for nombre, archivo in nombres:
                n+=1
                texto+=f'<code>{n}</code> {nombre}\n'
            bot.send_message(cid, texto, parse_mode = "html")
        else:
            indice = int(param[1])
            datos = nombres[indice-1]
            nombre = datos[0]
            icid, iuid = datos[1].split("_")
            res = bot.unban_chat_member(icid, iuid, only_if_banned=True)
            if res:
                # eliminamos el mensaje del comando
                bot.delete_message(cid, m.message_id)
                # informamos del desbaneo en el grupo
                bot.send_message(cid, f'<b>{nombre}</b> ha sido desbaneado', parse_mode = "html")
                os.remove(f'{Dic_avisos["baneados"]}/{datos[1]}')
            else:
                bot.send_message(cid, f'ERROR al desbanear a <b>{nombre}</b>', parse_mode = "html")
                

@bot.message_handler(func=lambda x: True)
def mensajes_recibidos(m):
    cid = m.chat.id #id del chat
    uid = m.from_user.id # id del usuario -> saber qué usuario envió el mensaje
    nombre = m.from_user.first_name #nombre del usuario
    #mostramos en la terminal el mensaje
    print(f'{nombre}: {m.text}')
    info_miembro = bot.get_chat_member(cid,uid)
    if not info_miembro.status in ["creator", "administrator"]:
        palabra_ofensiva = existe_malas_palabras(m.text)
        if palabra_ofensiva:
            # Cambiar el último carácter de la palabra grosera por ##
            palabra_modificada = palabra_ofensiva[:-1] + '#'
            # eliminamos el mensaje del usuario
            bot.delete_message(cid, m.message_id)
            avisar(cid, uid, nombre, palabra_modificada)

def avisar(cid, uid, nombre, palabra_ofensiva):
    if not os.path.isfile(f'{Dic_avisos["avisos"]}/{cid}_{uid}'):
        avisos = 1
    #si el archivo existe del usuario significa que ya tiene más de un aviso
    else:
        with open(f'{Dic_avisos["avisos"]}/{cid}_{uid}', "r", encoding="utf-8") as f:
            #leemos la primera línea del archivo (el número de avisos)
            avisos = int(f.read().split("\n")[0])
            avisos += 1
    texto = f'<b>AVISO</b> <code>{avisos}</code> de <code>{max_avisos}</code>\n'
    texto += f'Se ha borrado el texto de <b>{nombre}</b> por el uso de la palabra: <b>{palabra_ofensiva}</b>'
    bot.send_message(cid, texto, parse_mode="html")
    if avisos < max_avisos:
        with open(f'{Dic_avisos["avisos"]}/{cid}_{uid}', "w", encoding="utf-8") as f:
            f.write(f'{avisos}\n{nombre}')
    else:
        fin_ban = datetime.now() + timedelta(minutes=10) # fecha que finaliza el baneo/ después de esto el usuario puede volver a entrar en el grupo
        try: # banear al usuario
            bot.ban_chat_member(cid, uid, until_date = fin_ban)
        except telebot.apihelper.ApiTelegramException as e: #el try except controla que el creador no sea eliminado del grupo
            print(f'ERROR: {e}')
            return
        #informamos en el grupo al usuario que ha sido baneado por mala conducta
        print(f'{nombre} ({uid}) baneado por uso de insultos en el chat, hasta {fin_ban}')
        bot.send_message(cid, f'<b>{nombre}</b>({uid}) baneado por uso de groserías', parse_mode="html")
        # movemos el archivo del usuario a la carpeta de baneados
        move(f'{Dic_avisos["avisos"]}/{cid}_{uid}', f'{Dic_avisos["baneados"]}/{cid}_{uid}')

def generar_patron(palabra):
    # Reemplaza las vocales con grupos regex que incluyan sus variantes acentuadas
    palabra = re.sub(r'a', r'[aáä@*4]', palabra, flags=re.IGNORECASE)
    palabra = re.sub(r'e', r'[eéë@*3]', palabra, flags=re.IGNORECASE)
    palabra = re.sub(r'i', r'[iíï@*1]', palabra, flags=re.IGNORECASE)
    palabra = re.sub(r'o', r'[oóö@*0]', palabra, flags=re.IGNORECASE)
    palabra = re.sub(r'u', r'[uúüv@*]', palabra, flags=re.IGNORECASE)
    return palabra

# Generamos el patrón completo uniendo las palabras en una sola expresión regex
patrones_prohibidos = [generar_patron(palabra) for palabra in palabras_prohibidas]
patron_regex = r'\b(' + '|'.join(patrones_prohibidos) + r')\b'

def existe_malas_palabras(texto):
    for palabra in palabras_prohibidas:
        #si existe la palabra en el texto
        if re.search(r'\b' + palabra + r'\b', texto, flags=re.IGNORECASE):
            return palabra  # Retorna la palabra encontrada
    return None  # Si no se encuentra ninguna palabra prohibida


if __name__== '__main__':
    bot.infinity_polling(timeout=60)
