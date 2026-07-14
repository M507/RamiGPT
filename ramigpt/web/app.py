from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit
from functools import wraps
import os, logging, time

import threading
# Shared variable accessible to the background task and main application
stop_task_flag = threading.Event()
stop_full_ai = threading.Event()

from pwn import *
from ai import *
from PrivEscPrompt import *
from root_detection import *
from common import *
from setup_logger import *

FLASK_TEMPLATES_FOLDER = os.getenv("FLASK_TEMPLATES_FOLDER", "templates")
FLASK_STATIC_FILES_FOLDER = os.getenv("FLASK_STATIC_FILES_FOLDER", "static")
OPENAI_MAX_NUM_OF_REQS = int(os.getenv("OPENAI_MAX_NUM_OF_REQS", 10))
DEBUG = int(os.getenv("DEBUG", 0))

app = Flask(__name__, template_folder=FLASK_TEMPLATES_FOLDER, static_folder=FLASK_STATIC_FILES_FOLDER)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

ENTRY_TYPES = {
    "fact": {"add": "add_facts", "remove": "remove_fact"},
    "hint": {"add": "add_hint", "remove": "remove_hint"},
    "avoid": {"add": "add_avoid", "remove": "remove_avoid"},
    "demo": {"add": "add_demo", "remove": "remove_demo"}
}

socketio = SocketIO(app, ssl_context=('cert.pem', 'key.pem'))  # Add SSL certs


# Dictionary to hold SSH shells
ssh_shells = {}
ssh_ssh_conns = {}
prompt_delimiters = {}
prompts = {}
loop = {}
beroots = {}
last_commands = {}
timeout_default = 6
prompt_delimiter = b"$ "  # Assuming the prompt ends with $ and a space
shell_recvuntil_v4_list = []

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@socketio.on('connect', namespace='/get')
def test_connect():
    print('Client connected')
    #socketio.start_background_task(send_time)

@socketio.on('disconnect', namespace='/get')
def test_disconnect():
    print('Client disconnected')

def send_time():
    while True:
        socketio.sleep(1)  # Sleep for 1 second
        time_str = time.strftime('%H:%M:%S')  # Get current time
        socketio.emit('message', {'data': 'Current time: ' + time_str}, namespace='/get')

@app.route('/')
@login_required
def index():
    global stop_task_flag

    session_data_copy = session.copy()
    session_data_copy['sid'] = session.sid
    shell = ssh_shells.get(session.sid)

    stop_task_flag.clear()  # Make sure the flag is clear at the start
    socketio.start_background_task(shell_interaction, shell, socketio.emit, session_data_copy)
    return render_template('index.html', hostname = session['hostname'], username = session['username'])

@app.route('/login')
def login():
    return render_template('login.html')

def upload_beroot(ssh_conn):
    # Directory to be copied and destination
    local_path = 'external_tools/BeRoot-master/Linux'
    remote_path = '/tmp/'

    # Copy directory to server
    ssh_conn.upload(local_path, remote_path)
    socketio.emit('message', {'data': f'ssh_conn.upload uploading\n', 'color': "#1E90FF"}, namespace='/get')

    # Opening a shell
    shell = ssh_conn.process('/bin/sh', env={'TERM': ''})

    shell_output_bytes, \
    shell_output_lines, \
    shell_output_lines_string, \
    shell_output = shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default)
    debug_logger.debug(f"upload_beroot.shell_recvuntil() shell_output: {shell_output}\n")

    # Executing the specific command sequence
    command = """{ python3 /tmp/Linux/beroot.py --password '"""+session.get('password')+"""' || python /tmp/Linux/beroot.py --password '"""+session.get('password')+"""'; } 2>/dev/null | tee /tmp/output.txt; cp /tmp/output.txt /tmp/beroot.txt"""
    shell.sendline(command)
    socketio.emit('message', {'data': f'connecting shell.sendline(command)\n', 'color': "#1E90FF"}, namespace='/get')

    debug_logger.debug(f"python3 /tmp/Linux/beroot.py commnad")

    shell_output_bytes, \
    shell_output_lines, \
    shell_output_lines_string, \
    shell_output = shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default)
    
    debug_logger.debug(f"upload_beroot.shell_recvuntil() shell_output: {shell_output}\n")
    socketio.emit('message', {'data': f'shell_output: {shell_output}\n', 'color': "#1E90FF"}, namespace='/get')

    shell.close()

def get_or_create_ssh_shell(session_id, create_new=False):
    if session_id in ssh_shells:
        return ssh_shells[session_id]
    elif create_new:
        try:
            # SSH connection setup
            ssh_conn = ssh(
                user=session.get('username'),
                host=session.get('server'), 
                port=session.get('port'), 
                password=session.get('password')
            )
            ssh_conn.set_env('TERM', '')
            
            # Upload beroot files to the server
            upload_beroot(ssh_conn)

            # Opening a shell
            shell = ssh_conn.process('/bin/sh', env={'TERM': ''})
            shell_output_bytes, \
            shell_output_lines, \
            shell_output_lines_string, \
            shell_output = shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default)
            
            # Saving the shell and connection objects
            ssh_shells[session_id] = shell
            ssh_ssh_conns[session_id] = ssh_conn
            return shell
        except Exception as e:
            debug_logger.exception("Failed to create or use SSH shell.")
            raise e

@app.before_request
def check_authentication():
    # Allow unauthenticated access only to login and connect endpoints
    if 'logged_in' not in session and request.endpoint not in ['connect', 'login']:
        return redirect(url_for('login'))

@app.route('/connect', methods=['POST'])
def connect():
    try:
        credentials = request.get_json()
        username = credentials['username']
        password = credentials['password']
        server = credentials.get('server', 'default_host')
        hostname = credentials.get('hostname', "pehost")
        port = int(credentials.get('port', 22))
        if request.path == '/connect':
            session['logged_in'] = True
            session['username'] = username
            session['password'] = password
            session['server'] = server
            session['port'] = port
            session['hostname'] = hostname
            # Attempt to create SSH shell immediately after logging in
            session_id = session.sid
            try:
                shell = get_or_create_ssh_shell(session_id, create_new=True)
                
                priv_esc_prompt = PrivEscPrompt(username, password, "Linux", "root")
                prompts[session_id] = priv_esc_prompt
                prompt_delimiters[session_id] = b"$ "

                return jsonify(success=True)
            except Exception as e:
                return jsonify(success=False, error=str(e)), 500
        else:
            return jsonify(success=False), 401
    except Exception as e:
        socketio.emit('message', {'data': f"[ERROR] Failed to execute command - {e}"}, namespace='/get')
        debug_logger.exception("Failed to execute command.")
        return jsonify(error=str(e)), 500

@app.route('/get', methods=['GET'])
@login_required
def test():
    # formatted_string = template.format(cmd=cmd, resp=resp)
    time_str = time.strftime('%H:%M:%S')  # Get current time
    socketio.emit('message', {'data': 'Current time: 44' + time_str}, namespace='/get')
    return jsonify(output="response"), 200


def shell_conditions(command, shell, prompt_delimiter, session_data, just_got_root):
    # Handle special command cases
    if command.startswith("su "):
        while True:
            shell_output_bytes = recv_for_duration(shell, timeout_default)
            shell_output_lines = shell_output_bytes.decode('utf-8').split('\n')
            shell_output = shell_output_bytes.decode('utf-8').strip()
            priv_esc.add_history(f"{prompt_delimiter.decode('utf-8').strip()} {command}", shell_output)
            if len(shell_output) <= 0:
                break
            last_line = shell_output_lines[-1]
            if got_root(session_data.get('hostname'), last_line):
                prompt_delimiters[session_id] = last_line
                socketio.emit('message', {'data': f'{shell_output}\npwned!'}, namespace='/get')
                just_got_root = True
                summary = priv_esc.generate_summary()
                color = "#1E90FF"  # Determine the color based on your logic or data
                socketio.emit('message', {'data': f'{summary}\n', 'color': color}, namespace='/get')
                return 
                break
            if "Password:" in shell_output:
                debug_logger.info(f"Prompting for password: {shell_output}")
                shell.sendline(session_data.get('password'))
    if command.startswith("sudo ") and not command.startswith("sudo -l"):
        shell_output = recv_for_duration(shell, timeout_default).decode('utf-8').strip()
        priv_esc.add_history(f"{prompt_delimiter.decode('utf-8').strip()} {command}", shell_output)
        if f"password for {session_data.get('username')}" in shell_output:
            debug_logger.info(f"Sudo password required: {shell_output}")
            shell.sendline(session_data.get('password'))

    if "sudo " in command and not command.startswith("sudo -l"):
        priv_esc.add_history(f"{prompt_delimiter.decode('utf-8').strip()} {command}", shell_output)
        shell.sendline("!/bin/sh")
        priv_esc.add_history("!/bin/sh", shell_output)
        shell.sendline("id")
        priv_esc.add_history("id", shell_output)
        shell_output_bytes = recv_for_duration(shell, timeout_default)
        shell_output_lines = shell_output_bytes.decode('utf-8').split('\n')
        shell_output = shell_output_bytes.decode('utf-8').strip()
        for line in shell_output_lines:
            if got_root(session_data.get('hostname'), line):
                socketio.emit('message', {'data': f'{shell_output}\npwned!'}, namespace='/get')
                just_got_root = True
                prompt_delimiters[session_id] = shell_output_lines[-1]
                summary = priv_esc.generate_summary()
                color = "#1E90FF"  # Determine the color based on your logic or data
                socketio.emit('message', {'data': f'{summary}\n', 'color': color}, namespace='/get')
                return 
                break
    return command, shell, prompt_delimiter, session_data, just_got_root

def autonomous(session_data):
    global stop_task_flag
    global stop_full_ai

    with app.app_context():
        """Background task for a specific session using passed session data."""
        socketio.emit('message', {'data': f'Giving AI full freedom to send {OPENAI_MAX_NUM_OF_REQS} commands', 'color': "#1E90FF"}, namespace='/get')
        session_id = session_data['sid']
        debug_logger.info(f"Starting autonomous loop for session: {session_id}")
        i = 0
        just_got_root = False
        
        # Safely fetching session-specific data with default values and debugging
        prompt_delimiter = prompt_delimiters.get(session_id, "$")  # Default to "#" if not set
        shell = ssh_shells.get(session_id)
        priv_esc = prompts.get(session_id)

        # Debug initial state of the session-specific objects
        debug_logger.debug(f"autonomous(): Initial setup for session {session_id}: prompt_delimiter={prompt_delimiter}, shell={shell}, priv_esc={priv_esc}")
        
        while i < OPENAI_MAX_NUM_OF_REQS:  # Ensure the loop runs only if it's enabled
            if stop_full_ai.is_set():
                break
            socketio.sleep(1)  # Non-blocking sleep for better SocketIO handling
            i += 1
            try:
                socketio.emit('message', {'data': f"AI request#{i}======================================================================", 'color': "#FF0000"}, namespace='/get')
                debug_logger.debug(f"AI request#{i}======================================================================")
                
                # Create a prompt
                prompt = priv_esc.generate_prompt()
                if DEBUG:
                    socketio.emit('message', {'data': f"[DEBUG] About to send prompt:\n{prompt}"}, namespace='/get')
                
                debug_logger.debug(f"[DEBUG] About to send prompt:\n{prompt}")

                GlobalTimer.start()
                client = OpenAIClient()
                system = "You are an experienced pentester."
                response = get_answer(client, system, prompt)
                trimmed_ai_command = priv_esc.filter_output(response)
                command = remove_matching_quotes(trimmed_ai_command)
                
                debug_logger.info(f"Executing command: {command}")
                shell.sendline(command)
                socketio.emit('message', {'data': f"{prompt_delimiter.decode('utf-8').strip()} "+command}, namespace='/get')

                # command, \
                # shell, \
                # prompt_delimiter, \
                # session_data, \
                # just_got_root = shell_conditions(command, shell, prompt_delimiter, session_data, just_got_root)

                if not just_got_root:  
                    shell_output_bytes, \
                    shell_output_lines, \
                    shell_output_lines_string, \
                    shell_output = shell_recvuntil_v4(shell, prompt_delimiter, drop=False, timeout=1, session = session, emit_func = socketio.emit)
                    
                    # If it hangs
                    if shell_output == None:
                        socketio.emit('message', {'data': '[Debug] Autonomous() - timeout occurred, possibly stuck at prompt', 'color': "#FF0000"}, namespace='/get')
                        shell_output_bytes = recv_for_duration(shell, 4)
                        shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
                        shell_output        = shell_output_bytes.decode('utf-8').strip()
                        shell_output_lines_string = str(shell_output_lines)
                        socketio.emit('message', {'data': shell_output}, namespace='/get')
                        
                        shell.sendline("!/bin/sh")
                        priv_esc.add_history("!/bin/sh", shell_output)
                        shell.sendline("id")
                        priv_esc.add_history("id", shell_output)

                        shell_output_bytes = recv_for_duration(shell, 4)
                        shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
                        shell_output        = shell_output_bytes.decode('utf-8').strip()
                        shell_output_lines_string = str(shell_output_lines)

                        socketio.emit('message', {'data': shell_output}, namespace='/get')
                        socketio.emit('message', {'data': "Start interacting with the shell again", 'color': "#1E90FF"}, namespace='/get')
                        i = OPENAI_MAX_NUM_OF_REQS

                    last_line = shell_output_lines[-1]
                
                debug_logger.debug(f"[Debug] shell_output: {shell_output}")
                shell_output = priv_esc.remove_last_line(shell_output)
                shell_output = priv_esc.process_command_output(command, shell_output)
                command = last_line + command
                priv_esc.add_history(command, shell_output)
                
                prompt = priv_esc.generate_prompt()


                if got_root(session_data.get('hostname'), last_line):
                    GlobalTimer.stop(f"""Autonomous - Hostname:{session_data.get('hostname')}, Server:{session_data.get('server')}, Username:{session_data.get('username')}""".strip('\n'))
                    # prompt_delimiters[session_id] = last_line
                    socketio.emit('message', {'data': f'{shell_output}\npwned!'}, namespace='/get')
                    just_got_root = True
                    summary = priv_esc.generate_summary()
                    color = "#1E90FF"  # Determine the color based on your logic or data
                    socketio.emit('message', {'data': f'{summary}\n', 'color': color}, namespace='/get')
                    
                #output = command + "\n" + shell_output + "\n"
                #socketio.emit('message', {'data': output}, namespace='/get')
            except Exception as e:
                debug_logger.exception("Failed to execute command.")
                socketio.emit('message', {'data': f"Error: {str(e)}"}, namespace='/get')
                output = ""
                return 

def execute_beroot(session):
    """Background task for a specific session using passed session data."""
    session_id = session['sid']
    ssh_conn = ssh_ssh_conns.get(session_id)
    shell = ssh_shells.get(session_id)
    prompt_delimiter = prompt_delimiters.get(session_id, "$").decode('utf-8').strip()

    # Downloading the beroot.txt file
    local_filename = f"external_tools/BeRoot-master/Linux/downloaded/{session_id}_beroot.txt"
    ssh_conn.download('/tmp/beroot.txt', local_filename)
    socketio.sleep(1)  # Non-blocking sleep for better SocketIO handling
    
    # Logging successful download
    debug_logger.info(f"beroot.txt file downloaded successfully as {local_filename}")
    if DEBUG:
        socketio.emit('message', {'data': f"beroot.txt file downloaded successfully as {local_filename}"}, namespace='/get')
    
    beroots[session_id] = local_filename

    beroot_file = beroots[session_id]
    beroot_string = read_file_to_string(beroot_file)
    
    priv_esc = prompts.get(session_id)
    priv_esc.set_BeRoot(beroot_string)

    socketio.emit('message', {'data': f"[EXCUTION] BeRoot:\n{beroot_string}", 'color': "#FF0000"}, namespace='/get')

    # Create a prompt
    prompt = priv_esc.generate_prompt()
    if DEBUG:
        socketio.emit('message', {'data': f"[DEBUG] About to send prompt:\n{prompt}"}, namespace='/get')
     
    client = OpenAIClient()
    system = "You are an experienced pentester."
    response = get_answer(client, system, prompt)
    trimmed_ai_command = priv_esc.filter_output(response)
    command = remove_matching_quotes(trimmed_ai_command)
    #socketio.emit('message', {'data': f"[DEBUG] About to execute command:\n{command}"}, namespace='/get')
    
    debug_logger.info(f"Executing command: {command}")
    shell.sendline(command)
    last_commands[session_id] = command
    socketio.emit('message', {'data': f"{prompt_delimiter} {command}"}, namespace='/get')


@app.route('/action3', methods=['POST', 'DELETE'])
@login_required
def action3():
    debug_logger.debug("Received request at /action3 endpoint.")
    
    if not request.is_json:
        debug_logger.warning("Request does not contain JSON data.")
        return jsonify(error="Invalid request format."), 400

    action = request.json.get('action', '').strip()
    debug_logger.debug(f"Action received: {action}")

    if not action:
        debug_logger.warning("No action specified in the request.")
        return jsonify(error="Missing action parameter."), 400

    time_str = time.strftime('%H:%M:%S')  # Get current time


    if action == "start":
        loop[session.sid] = 1
        # Start the background task with session data
        session_data_copy = session.copy()
        session_data_copy['sid'] = session.sid
        socketio.start_background_task(execute_beroot, session_data_copy)
        socketio.emit('message', {'data': 'Starting..'}, namespace='/get')

    elif action == "stop":
        loop[session.sid] = 0
        debug_logger.info(f"Action '{action}' triggered at {time_str}. Emitting 'Stopping..' message.")
        socketio.emit('message', {'data': 'Stopping..'}, namespace='/get')

    else:
        debug_logger.warning(f"Invalid action received: {action}")
        return jsonify(error="Invalid action specified."), 400

    return jsonify(output="response"), 200


@app.route('/action1', methods=['POST', 'DELETE'])
@login_required
def action1():
    global stop_full_ai

    debug_logger.debug("Received request at /action1 endpoint.")
    
    if not request.is_json:
        debug_logger.warning("Request does not contain JSON data.")
        return jsonify(error="Invalid request format."), 400

    action = request.json.get('action', '').strip()
    debug_logger.debug(f"Action received: {action}")

    if not action:
        debug_logger.warning("No action specified in the request.")
        return jsonify(error="Missing action parameter."), 400

    time_str = time.strftime('%H:%M:%S')  # Get current time

    # Prepare session data for the background task
    session_data = {
        'sid': session.sid,
        'username': session.get('username'),
        'password': session.get('password'),
        'hostname': session.get('hostname')
    }

    if action == "start":
        stop_full_ai.clear()
        loop[session.sid] = 1
        # Start the background task with session data
        socketio.start_background_task(autonomous, session_data)

    elif action == "stop":
        stop_full_ai.set()  # Signal the task to stop
        loop[session.sid] = 0
        debug_logger.info(f"Action '{action}' triggered at {time_str}. Emitting 'Stopping..' message.")
        socketio.emit('message', {'data': 'Stopping..'}, namespace='/get')

    else:
        debug_logger.warning(f"Invalid action received: {action}")
        return jsonify(error="Invalid action specified."), 400

    return jsonify(output="response"), 200

def receive_shell_output(shell, prompt_delimiter, timeout_default=0.5, max_timeout=2):
    """ 
    Receives shell output line by line until the prompt delimiter is found 
    or a consecutive timeout of max_timeout seconds occurs.
    """
    shell_output = b""  # Use bytes initially to avoid decoding issues
    consecutive_timeout = 0  # Track consecutive timeout duration

    while True:
        try:
            line = shell.recv(timeout=timeout_default)  # Read small chunks with timeout

            if line:
                shell_output += line  # Append received bytes
                consecutive_timeout = 0  # Reset timeout counter

                # Stop if the prompt delimiter is detected
                if prompt_delimiter.encode() in shell_output:
                    break
            else:
                consecutive_timeout += timeout_default  # Accumulate timeout duration
                if consecutive_timeout >= max_timeout:
                    break  # Stop if timeout exceeds 2 seconds

        except Exception as e:
            break  # Handle unexpected errors gracefully

    return shell_output.decode('utf-8', errors='ignore').strip()  # Decode safely

def recv_for_duration(shell, duration):
    end_time = time.time() + duration
    data = b''
    while time.time() < end_time:
        try:
            remaining_time = end_time - time.time()
            if remaining_time <= 0:
                break
            new_data = shell.recv(timeout=remaining_time)
            if new_data:
                data += new_data
        except EOFError:
            break  # Stop if the connection is closed
    return data

def shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default):
    shell_output_bytes  = shell.recvuntil(prompt_delimiter, drop=False, timeout=timeout_default)
    shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
    shell_output        = shell_output_bytes.decode('utf-8').strip()
    shell_output_lines_string = str(shell_output_lines)
    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output

def shell_recvuntil_v2(shell, prompt_delimiter, drop=False, timeout=timeout_default, session = None, emit_func = None):
    debug_logger.info(f"shell_recvuntil_v2() :{line}")
    shell_output_bytes  = shell.recvuntil(prompt_delimiter, drop=False, timeout=timeout_default)
    shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
    shell_output        = shell_output_bytes.decode('utf-8').strip()
    shell_output_lines_string = str(shell_output_lines)
    if f"Password:" in shell_output:
        if emit_func != None:
            if DEBUG:
                emit_func('message', {'data': f"[Debug] Password:"}, namespace='/get')
        debug_logger.info(f"if Password: in line:{line}")
        shell.sendline(session.get('password'))  # Send the sudo password
    if f"password for {session.get('username')}" in shell_output:
        if emit_func != None:
            if DEBUG:
                emit_func('message', {'data': f"[Debug] Password:"}, namespace='/get')
        debug_logger.info(f"Sudo password required: {shell_output}")
        shell.sendline(session.get('password'))
    if emit_func != None:
        if DEBUG:
            emit_func('message', {'data': f"[Debug] shell_recvuntil_v2:{shell_output_lines_string}"}, namespace='/get')
    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output

def shell_recvuntil_v3(shell, prompt_delimiter, drop=False, timeout=timeout_default, session=None, emit_func=None):
    try:
        shell_output_bytes = shell.recvuntil(prompt_delimiter, drop=drop, timeout=timeout)
    except TimeoutError:
        # Handle the case where the recvuntil times out, possibly due to a sudo password prompt
        if emit_func:
            emit_func('message', {'data': '[Debug] Timeout occurred, possibly stuck at prompt'}, namespace='/get')
        debug_logger.warning("Timeout occurred, attempting to handle sudo password prompt")
        
        shell.sendline(session.get('password'))  # Attempt to send the password
        shell_output_bytes = shell.recvuntil(prompt_delimiter, drop=drop, timeout=timeout)  # Try to receive again

    shell_output = shell_output_bytes.decode('utf-8')
    shell_output_lines = shell_output.split('\n')
    shell_output_lines_string = str(shell_output_lines)

    # Additional logging for debug information
    if emit_func:
        if DEBUG:
            emit_func('message', {'data': f"[Debug] shell_recvuntil_v2:{shell_output_lines_string}"}, namespace='/get')
    
    # Logging the output for debugging
    debug_logger.info(f"shell_recvuntil_v2() output: {shell_output}")

    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output

def shell_recvuntil_v4(shell, prompt_delimiter, drop=False, timeout=timeout_default, session=None, emit_func=None):
    with app.app_context():
        shell_output_bytes = b""
        shell_output = shell_output_bytes.decode('utf-8')
        shell_output_lines = shell_output.split('\n')
        shell_output_lines_string = str(shell_output_lines)
        
        #emit_func('message', {'data': '[Debug] shell_recvuntil_v4()', 'color': "#FF0000"}, namespace='/get')

        try:
            shell_output_bytes = shell.recvuntil(prompt_delimiter, drop=drop, timeout=timeout)
            #shell_output_bytes = shell.recv(drop=drop, timeout=timeout)
        except TimeoutError:
            # Handle the case where the recvuntil times out, possibly due to a sudo password prompt
            #emit_func('message', {'data': f"[Debug] {shell_output_lines_string}", 'color': "#1E90FF"}, namespace='/get')
            emit_func('message', {'data': '[Debug] Timeout occurred, possibly stuck at prompt', 'color': "#FF0000"}, namespace='/get')
            debug_logger.warning("Timeout occurred, attempting to handle sudo password prompt")
            return None, None, None, None
        except Exception as e:
            #emit_func('message', {'data': f"[Debug] {shell_output_lines_string}", 'color': "#1E90FF"}, namespace='/get')
            debug_logger.error(f"Unexpected error in shell_recvuntil_v4: {str(e)}")
            emit_func('message', {'data': f"[Debug] shell_recvuntil_v4 - Error: {str(e)}", 'color': "#FF0000"}, namespace='/get')
            return None, None, None, None

        shell_output = shell_output_bytes.decode('utf-8')
        shell_output_lines = shell_output.split('\n')
        shell_output_lines_string = str(shell_output_lines)

        if len(shell_output_lines) == 1:
            if len(shell_output_lines[0]) == 0:
                #emit_func('message', {'data': f"[Debug] {shell_output_lines_string}", 'color': "#1E90FF"}, namespace='/get')
                emit_func('message', {'data': '[Debug] Empty response from shell, possibly stuck at prompt', 'color': "#FF0000"}, namespace='/get')
                return None, None, None, None

        emit_func('message', {'data': f"{shell_output}"}, namespace='/get')

        return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output
    return None, None, None, None

def shell_interaction(shell, emit_func, session, max_retries=1000000):
    with app.app_context():
        debug_logger.debug("[Debug] Entering shell_interaction")
        session_id = session['sid']
        shell = ssh_shells.get(session_id)
        priv_esc = prompts.get(session_id)
        prompt_delimiter = prompt_delimiters.get(session_id, "$").strip()
        emit_func('message', {'data': "[Debug] Starting shell interaction", 'color': "#1E90FF"}, namespace='/get')
        
        retries = 0
        
        while True:
            try:
                while True:
                    socketio.sleep(1)
                    #emit_func('message', {'data': f"[LOOP] 1\n", 'color': "#1E90FF"}, namespace='/get')
                    while not stop_task_flag.is_set():
                        #emit_func('message', {'data': f"[LOOP] 2\n", 'color': "#1E90FF"}, namespace='/get')
                        shell = ssh_shells.get(session_id)
                        socketio.sleep(1)
                        data = shell.recv(timeout=1)
                        if data:
                            prompt_delimiter = prompt_delimiters.get(session_id, "$").decode('utf-8').strip()
                            decoded_data = data.decode('utf-8').strip()
                            command = last_commands[session_id]
                            decoded_data = priv_esc.process_command_output(command, decoded_data)
                            priv_esc.add_history(f"{prompt_delimiter} " + command, decoded_data)
                            prompt = priv_esc.generate_prompt()

                            debug_logger.debug(f"[Debug] shell_interaction() Data received: {decoded_data}\nprompt:{prompt}")
                            emit_func('message', {'data': f"{decoded_data}\n"}, namespace='/get')

            except EOFError:
                debug_logger.error("[Debug] EOFError: Shell stream closed.")
                emit_func('message', {'data': "[Debug] Shell stream closed", 'color': "#FF0000"}, namespace='/get')
                retries += 1
                if retries < max_retries:
                    debug_logger.info(f"Retrying shell interaction... Attempt {retries + 1}")
                continue
            
            except Exception as e:
                #debug_logger.error(f"Unexpected error in shell_interaction: {str(e)}")
                #emit_func('message', {'data': f"[Debug] Unexpected error in shell_interaction: {str(e)}", 'color': "#FF0000"}, namespace='/get')
                retries += 1
                if retries < max_retries:
                    debug_logger.info(f"Retrying shell interaction... Attempt {retries + 1}")
                continue

            break  # Exit loop if no exceptions are raised
        
        debug_logger.debug("[Debug] Exiting shell_interaction")
        emit_func('message', {'data': "[Debug] Exiting shell interaction", 'color': "#FF0000"}, namespace='/get')

def recreate_shell(emit_func, session_id):
    message = 'Exiting /bin/sh'
    debug_logger.debug(message)
    emit_func('message', {'data': message}, namespace='/get')
    ssh_conn = ssh_ssh_conns[session_id]
    shell = ssh_conn.process('/bin/sh', env={'TERM': ''})
    ssh_shells[session_id] = shell
    # After you start a new shell, drain the buffer using the recv function \/ 
    shell_output_bytes, \
    shell_output_lines, \
    shell_output_lines_string, \
    shell_output = shell_recvuntil_v2(shell, prompt_delimiter, drop=False, timeout=timeout_default, session = session)
    return jsonify(output='Started a new /bin/sh process'), 200

@app.route('/execute', methods=['POST'])
@login_required
def execute():
    global stop_task_flag
    stop_task_flag.clear()  # Make sure the flag is clear at the start

    # Debugging statement to log each request to this endpoint
    debug_logger.debug("Received a POST request to /execute")
    # socketio.emit('message', {'data': "Received a POST request to /execute"}, namespace='/get')

    # Check if the user is logged in
    if 'logged_in' not in session:
        debug_logger.warning("Attempt to execute command without authentication.")
        return jsonify(error="Unauthorized"), 401

    # Logging session ID for debugging
    session_id = session.sid
    debug_logger.debug(f"Session ID: {session_id}")
    try:
        try:
            # Initialize variables and fetch session specific objects
            trimmed_ai_command = ""
            just_got_root = False
            prompt_delimiter = prompt_delimiters.get(session_id, "$")  
            shell = ssh_shells.get(session_id)
            priv_esc = prompts.get(session_id)

            # Debugging statements to log fetched objects and initial values
            debug_logger.debug(f"Initial trimmed_ai_command: {trimmed_ai_command}")
            debug_logger.debug(f"Initial just_got_root: {just_got_root}")
            debug_logger.debug(f"Prompt delimiter for session {session_id}: {prompt_delimiter}")
            debug_logger.debug(f"Shell object for session {session_id}: {shell}")
            debug_logger.debug(f"Privilege escalation object for session {session_id}: {priv_esc}")

        except Exception as e:
            debug_logger.error(f"An error occurred while executing command: {str(e)}", exc_info=True)
            return jsonify(error=str(e)), 500

        # Create a prompt
        prompt = priv_esc.generate_prompt()

        command = request.json.get('command', '')
        if command == "exit":
            return recreate_shell(socketio.emit, session_id)

        if len(command) < 1:
            client = OpenAIClient()
            system = "You are an experienced pentester."
            #socketio.emit('message', {'data': f"[DEBUG] About to send prompt:\n{prompt}"}, namespace='/get')
            response = get_answer(client, system, prompt)
            trimmed_ai_command = priv_esc.filter_output(response)
            trimmed_ai_command = remove_matching_quotes(trimmed_ai_command)
            command = trimmed_ai_command
            #socketio.emit('message', {'data': f"[DEBUG] About to send command:\n{command}\nFrom {response}"}, namespace='/get')

        debug_logger.info(f"Executing command: {command}")

        last_commands[session_id] = command
        shell.sendline(command)
        socketio.emit('message', {'data': f"{prompt_delimiter.decode('utf-8').strip()} "+command}, namespace='/get')

        output = ""
        return jsonify(output=output), 200
    except Exception as e:
        socketio.emit('message', {'data': f"[ERROR] Failed to execute command - {e}"}, namespace='/get')
        debug_logger.exception("Failed to execute command.")
        return jsonify(error=str(e)), 500

def modify_entry(entry_type, action):
    """ Generic function to add or remove an entry dynamically. """
    debug_logger.debug(f"Received request to {action} {entry_type}.")

    if 'logged_in' not in session:
        debug_logger.warning("Unauthorized access attempt.")
        return jsonify(error="Unauthorized"), 401

    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        debug_logger.warning("Invalid or empty input received.")
        return jsonify(success=False, message="Invalid or empty input."), 400

    session_id = session.sid
    priv_esc = prompts.get(session_id)
    if not priv_esc:
        debug_logger.error(f"Session error: No privilege escalation object found for session {session_id}.")
        return jsonify(success=False, message="Session error."), 500

    # Get the correct function dynamically
    function_name = ENTRY_TYPES.get(entry_type, {}).get(action)
    if not function_name:
        debug_logger.error(f"Invalid entry type '{entry_type}' or action '{action}' requested.")
        return jsonify(success=False, message="Invalid operation."), 400

    if not hasattr(priv_esc, function_name):
        debug_logger.error(f"Function '{function_name}' does not exist on the privilege escalation object.")
        return jsonify(success=False, message="Invalid operation."), 400

    try:
        # Execute the function dynamically
        getattr(priv_esc, function_name)(text)
        debug_logger.info(f"Successfully {action}d {entry_type}: {text}")
        return jsonify(success=True, message=f"{entry_type.capitalize()} {action}d successfully."), 200
    except Exception as e:
        debug_logger.exception(f"Error occurred while executing {function_name} for {entry_type}: {e}")
        return jsonify(success=False, message="Internal server error."), 500

# Single route for adding and deleting entries
@app.route('/<entry_type>', methods=['POST', 'DELETE'])
@login_required
def handle_entry(entry_type):
    if entry_type in ENTRY_TYPES:
        action = "add" if request.method == "POST" else "remove"
        return modify_entry(entry_type, action)
    return jsonify(success=False, message="Invalid entry type."), 400

@app.route('/logout')
def logout():
    session_id = session.sid
    if session_id in ssh_shells:
        ssh_shells[session_id].close()  # Close the shell
        del ssh_shells[session_id]  # Remove from global dictionary
    session.pop('logged_in', None)
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, keyfile='key.pem', certfile='cert.pem')

