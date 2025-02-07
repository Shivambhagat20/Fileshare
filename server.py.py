import base64
import socket
import select
import os
import json
from datetime import datetime

# Using text file for metadata
METADATA_FILE = "metadata.txt"
UPLOADS_DIR = "uploads"

# Initialize metadata file and uploads directory
if not os.path.exists(UPLOADS_DIR):
    os.mkdir(UPLOADS_DIR)

if not os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, "w") as f:
        json.dump([], f)

def load_metadata():
    with open(METADATA_FILE, "r") as f:
        return json.load(f)

def save_metadata(metadata):
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

def update_metadata(filename, new_data):
    metadata = load_metadata()
    for data in metadata:
        if data["filename"] == filename:
            metadata.remove(data)
    metadata.append(new_data)
    save_metadata(metadata)

class TreeDriveServer:
    def __init__(self, host='', port=8240):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((host, port))
        self.server_sock.listen()
        self.clients = {}
        self.user_sessions = []
        self.file_chunks = {} 

    def handle_client(self, client_sock):
        try:
            data = client_sock.recv(4096).decode('utf-8').strip()
            if data:
                command = json.loads(data)
                print(command, end='\n')
                if command['command']== 'LOGIN':
                    self.login(client_sock, command)
                elif command['command'] == 'PUSH':
                    self.upload_chunk(client_sock, command)
                elif command["command"] == "UPLOAD_COMPLETE":
                    self.complete_upload(client_sock, command)    
                elif command['command'] == 'GET':
                    self.download(client_sock, command)
                elif command['command'] == 'LIST':
                    self.list_files(client_sock)
                elif command['command'] == 'DELETE':
                    self.delete_file(client_sock, command)
                else:
                    client_sock.send(b'Invalid command\n')
        except Exception as e:
            print(f"Error handling client: {e}")
            client_sock.send(b'Error processing command\n')
    
    # Function decorator to ensure all functions requiring auth are performed while logged in
    def check_logged_in(func):
        def wrapper(self, client_sock, command):
            username = command.get('username')
            if username not in self.user_sessions:
                client_sock.send(b'Please log in first\n')
                return
            return func(self, client_sock, command)  
        return wrapper


    def login(self, client_sock, command):
        username = command['username']
        self.user_sessions.append(username)
        client_sock.send(b'Login successful\n')

    @check_logged_in
    def upload_chunk(self, client_sock, command):
        # handle file chunks seperately
        filename = command["filename"]
        chunk_number = command["chunk_number"]
        chunk_data = base64.b64decode(command["data"]) 

        if filename not in self.file_chunks:
            self.file_chunks[filename] = []

        self.file_chunks[filename].append((chunk_number, chunk_data))

        client_sock.send(f"Chunk {chunk_number} received\n".encode())
    
    def complete_upload(self, client_sock, command):
        # using the chunks, rebuild and save the complete file version
        filename = command["filename"]
        if filename not in self.file_chunks:
            client_sock.send(b"Error: No chunks received\n")
            return

        # Sort chunks in order
        sorted_chunks = sorted(self.file_chunks[filename], key=lambda x: x[0])
        file_path = os.path.join(UPLOADS_DIR, filename)

        with open(file_path, "wb") as file:
            for _, chunk in sorted_chunks:
                file.write(chunk)

        del self.file_chunks[filename] 
        
        new_data = {
            "filename" : filename,
            "owner"    : command['username'],
            "size": command['size'],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        update_metadata(filename, new_data)
        
        client_sock.send(b"File uploaded successfully\n")

    @check_logged_in
    def download(self, client_sock, command):
        # Sends a file chunk to the client.
        filename = command["filename"]
        chunk_number = command["chunk_number"]
        chunk_size = command["chunk_size"]
        file_path = os.path.join(UPLOADS_DIR, filename)

        if not os.path.exists(file_path):
            client_sock.send(json.dumps({"error": "File not found"}).encode())
            return

        with open(file_path, "rb") as file:
            file.seek(chunk_number * chunk_size)
            chunk_data = file.read(chunk_size)
            
            # True if we are on the last chunk
            end_of_file = len(chunk_data) < chunk_size  

        response = {
            "filename": filename,
            "chunk_number": chunk_number,
            "data": base64.b64encode(chunk_data).decode('utf-8'),
            "end_of_file": end_of_file
        }

        client_sock.send(json.dumps(response).encode())

    def list_files(self, client_sock):

        metadata = load_metadata()
        user_files = [entry for entry in metadata]
        client_sock.send(json.dumps(user_files, indent=2).encode('utf-8'))

    @check_logged_in
    def delete_file(self, client_sock, command):

        filename = command['filename']
        metadata = load_metadata()
        username = command['username']

        file_entry = next((entry for entry in metadata if entry["filename"] == filename and entry["owner"] == username), None)
        if not file_entry:
            client_sock.send(b'File not found or unauthorized\n')
            return

        file_path = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        metadata.remove(file_entry)
        save_metadata(metadata)
        client_sock.send(b'File deleted successfully\n')

    def run(self):
        print(f"Server running on {self.server_sock.getsockname()}")
        while True:
            readable, _, _ = select.select([self.server_sock] + list(self.clients), [], [])
            for sock in readable:
                if sock == self.server_sock:
                    conn, addr = self.server_sock.accept()
                    print(f"Connected by {addr}")
                    self.clients[conn] = addr
                else:
                    self.handle_client(sock)

server = TreeDriveServer()
server.run()
