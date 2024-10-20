import socket
import pyaudio
import struct
import threading
import time
from queue import Queue

# Conexiones de sockets para audio y comandos
audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
audio_socket.connect(("192.168.1.24", 5544))

command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
command_socket.connect(("192.168.1.24", 5533))

p = pyaudio.PyAudio()
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
volume = 1.0
paused = False  # Bandera de pausa
stopped = False  # Bandera de detención

# Inicializar el stream de PyAudio
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK)

# Cola para almacenar los datos de audio
audio_queue = Queue()

# Función para recibir comandos desde el servidor
def receive_commands():
    global volume, paused, stopped
    
    while True:
        response = command_socket.recv(CHUNK).decode('utf-8')
        if not response:
            print("Se cerró la conexión del socket de comandos.")
            break
        
        print(response)

        if response.startswith('volume:'):
            new_volume = float(response.split(':')[1]) / 100
            volume = new_volume
        
        elif response.startswith('pause'):
            paused = True
            print("Audio pausado.")
        
        elif response.startswith('resume'):
            paused = False
            print("Audio resumido.")
        
        elif response.startswith('stop'):
            global stopped  
            stopped = True
            print("Audio detenido.")
            while not audio_queue.empty():
                audio_queue.get()  # Se limpia la cola de audio
            continue  # Se vuelve al inicio del bucle para seguir escuchando comandos

# Hilo para procesar y reproducir el audio desde la cola
def process_audio():
    global paused, stopped
    
    while True:
        if stopped:
            stream.stop_stream()
            audio_queue.get()
            stream.start_stream()
            stopped = False  # Se resetea el estado de detenido
            continue  # Continuar recibiendo audio si hay nueva transmisión
            
        if not paused and not audio_queue.empty():
            data = audio_queue.get()
            try:
                audio_data = struct.unpack('<' + ('h' * CHUNK * CHANNELS), data)
            except struct.error as e:
                print(f"Error al desempaquetar datos: {e}")
                continue

            # Para ajustar el volumen de los datos de audio
            adjusted_audio_data = [max(-32768, min(32767, int(sample * volume))) for sample in audio_data]
            data = struct.pack('<' + ('h' * CHUNK * CHANNELS), *adjusted_audio_data)
            stream.write(data)
        else:
            # Se espera un poco si está pausado o no hay datos en la cola
            time.sleep(0.01)

# Hilo para manejar comandos
command_thread = threading.Thread(target=receive_commands)
command_thread.start()

# Hilo para procesar y reproducir audio
audio_thread = threading.Thread(target=process_audio)
audio_thread.start()

# Bucle principal para recibir datos de audio
while True:
    data = b''  # Buffer para recibir datos
    while len(data) < CHUNK * 2 * CHANNELS:
        packet = audio_socket.recv(CHUNK * 2 * CHANNELS - len(data))
        if not packet:
            break
        data += packet
    
    if len(data) < CHUNK * 2 * CHANNELS:
        print("Datos insuficientes recibidos, saliendo del bucle.")
        break

    # Se colocan los datos de audio en la cola para su procesamiento
    audio_queue.put(data)

# Se finaliza el stream y se cierra PyAudio
stream.stop_stream()
stream.close()
p.terminate()
