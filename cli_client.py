import socket
import json
import os
import base64
import math
from pathlib import Path as path

HOST = '' # '130.179.28.113'  # eagle.cs.umanitoba.ca
PORT = 8000 # 8240         

user_log_state = {'logged_in': False}
current_dir = path.cwd()

def print_files(args):
    global current_dir
    
    try:
        # Default to current directory if no path specified
        target_path = current_dir
        if args:
            target_path = (current_dir / args[0]).resolve()
            
        if not target_path.exists():
            print(f"Path does not exist: {target_path}")
            return
            
        # Get directory contents
        items = list(target_path.iterdir())
        
        # Sort items (directories first then files)
        dirs = sorted([item for item in items if item.is_dir()])
        files = sorted([item for item in items if item.is_file()])
        
        # Print directories and then files respectively
        for d in dirs:
            print(f"{d.name}/")
            
        for f in files:
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f}KB"
            else:
                size_str = f"{size/(1024*1024):.1f}MB"
            print(f"{f.name:<30} {size_str:>10}")
    except Exception as e:
        print(f"Error listing directory conmtent: {e}")

# cd
def change_dir(args):
    global current_dir
    
    # cd without any arguments goes to the home directory
    if not args:
        new_path = path.home()
    else:
        path_arg = args[0]
        if path_arg == '..':
            new_path = current_dir.parent
        elif path_arg == '~':
            new_path = path.home()
        else:
            new_path = (current_dir / path_arg).resolve()
    
    # Verify the path exists and is a directory
    try:
        if not new_path.exists():
            print(f"Path does not exist: {new_path}")
            return
        if not new_path.is_dir():
            print(f"Not a directory: {new_path}")
            return
            
        os.chdir(new_path)
        current_dir = new_path
        print(f"Current directory: {current_dir}")
    except Exception as e:
        print(f"Error changing directory: {e}")

def send_command(command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            # Send the command as a JSON string
            print(command)
            s.sendall(json.dumps(command).encode('utf-8') + b'\n')
            # Receive the server's response
            data = s.recv(4096)
            print('Server response:', repr(data), end='\n')
    except ConnectionRefusedError:
        print("Connection Error: Could not connect to the server. Is the server running?", end='\n')
    except Exception as e:
        print(f"Error: {e}", end='\n')
    else:
        if command['command'] == 'GET':
            return data

def file_upload(file_name):
    if not os.path.exists(file_name):
        print("File not found.")
        return
    
    file_size = os.path.getsize(file_name)
    print(f"Uploading '{file_name}' ({file_size} bytes) in chunks...")

    with open(file_name, "rb") as file:
        chunk_number = 0
        chunks = math.ceil(file_size/1024)
        while True:
            chunk = file.read(1024)
            
            # End of file
            if not chunk:
                break  
            
            command = {
                "command": "PUSH",
                "filename": file_name,
                "chunk_number": chunk_number,
                "chunk_size": len(chunk),
                "data": base64.b64encode(chunk).decode('utf-8'),
                'username': user_log_state['user']
            }
            send_command(command)
            chunk_number += 1

    # notify server that upload is complete
    final_message = {
        "command": "UPLOAD_COMPLETE",
        "size": file_size,
        "filename": file_name,
        "username": user_log_state['user']
    }
    send_command(final_message)

# Download file in chunks
def download_file(filename):
    os.makedirs("downloads", exist_ok=True)
    save_path = os.path.join("downloads", filename)
    

    chunk_number = 0
    with open(save_path, "w+b") as file:
        while True:
            command = {
                "command": "GET",
                "filename": filename,
                "chunk_number": chunk_number,
                "chunk_size": 1024,
                "username": user_log_state['user']
            }
            response = send_command(command)
            
            # Decode JSON response
            try:
                response = json.loads(response)
                print(response)
            except json.JSONDecodeError:
                print("Server sent invalid data.")
                break
            except Exception as e:
                print(f" Error with response: {e}")
                
            if "error" in response:
                print(response["error"])
                break
            
            chunk_data = base64.b64decode(response["data"])
            file.write(chunk_data)

            if response["end_of_file"]:
                print("Download complete!")
                break

            chunk_number += 1

def getfile(filename):
    try:
        with open(filename, 'rb') as file:
            # return file.read().decode('utf-8')
            return base64.b64encode(file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None

def main():
    
    while True:
        try:
            user_input = input("Available Commands: login/push<file>/get<file>/list/delete<file>/EXIT/ls/cd): ").strip().split()
            if not user_input:
                continue

            command = user_input[0].upper()
            args = user_input[1:]

            if command == "EXIT":
                print("Exiting client.")
                break

            # Build the command dictionary based on the user's input
            cmd_dict = {"command": command}

            if command == "LOGIN":
                if len(args) < 1:
                    print("Usage: login <username>")
                    continue
                cmd_dict["username"] = args[0]
                send_command(cmd_dict)
                # Update login state (assumes the server responds with success)
                user_log_state['logged_in'] = True
                user_log_state['user'] = args[0]

            elif command == "PUSH":
                if not user_log_state['logged_in']:
                    print("Please log in before trying to upload files.")
                    continue
                else:
                    cmd_dict['username'] = user_log_state['user']
                if len(args) < 1:
                    print("Usage: upload <file_path>")
                    continue
            
                print("Uploading file ...")
                file_upload(args[0])

            elif command == "GET":
                if not user_log_state['logged_in']:
                    print("Please log in before trying to downloading files.")
                    continue
                else:
                    cmd_dict['username'] = user_log_state['user']
                if len(args) < 1:
                    print("Usage: download <file_name>")
                    continue
                download_file(args[0])

            elif command == "LIST":
                send_command(cmd_dict)

            elif command == "DELETE":
                if not user_log_state['logged_in']:
                    print("Please log in before trying to downloading files.")
                    continue
                else:
                    cmd_dict['username'] = user_log_state['user']
                if len(args) < 1:
                    print("Usage: delete <file_name>")
                    continue
                cmd_dict["filename"] = args[0]
                send_command(cmd_dict)
                
            elif command == "PWD":
                print(current_dir)
                continue
            elif command == "LS":
                print_files(args)
                continue
            elif command == "CD":
                change_dir(args)
                continue
            
            else:
                print("Invalid command. Available commands: login, push, get, list, delete, exit, ls, cd")

        except KeyboardInterrupt:
            print("\nExiting client.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()