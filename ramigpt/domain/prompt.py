import re

class PrivEscPrompt:
    def __init__(self, username, password, system, target_user):
        self.username = username
        self.password = password
        self.system = system
        self.target_user = target_user
        self.BeRoot = None
        self.capabilities = []  # This will now be a list of dictionaries
        self.history = []
        self.facts = []  # List to store multiple facts
        self.hints = []   # List to store multiple hints
        self.avoids = []   # List to store multiple avoids

    def add_capability(self, name, description):
        # Adds a new capability to the list
        self.capabilities.append({"name": name, "description": description})
    
    def set_BeRoot(self, BeRoot):
        # Capabilities are expected to be a list of dictionaries with 'name' and 'description'
        self.BeRoot = BeRoot
    
    def get_BeRoot(self, capabilities):
        # Capabilities are expected to be a list of dictionaries with 'name' and 'description'
        return self.BeRoot

    def set_capabilities(self, capabilities):
        # Capabilities are expected to be a list of dictionaries with 'name' and 'description'
        self.capabilities = capabilities

    def add_history(self, command, output=""):
        # Prevent duplicates
        if not any(entry["output"] == output for entry in self.history):
            self.history.append({"command": command, "output": output})

    # Generic add function to prevent duplicates
    def add_entry(self, entry_list, entry):
        if entry not in entry_list:
            entry_list.append(entry)

    # Generic remove function
    def remove_entry(self, entry_list, entry):
        if entry in entry_list:
            entry_list.remove(entry)
            return True  # Successfully removed
        return False  # Entry not found

    # Fact management
    def add_facts(self, fact):
        self.add_entry(self.facts, fact)

    def remove_fact(self, fact):
        return self.remove_entry(self.facts, fact)

    # Hint management
    def add_hint(self, hint):
        self.add_entry(self.hints, hint)

    def remove_hint(self, hint):
        return self.remove_entry(self.hints, hint)

    # Avoid management
    def add_avoid(self, avoid):
        self.add_entry(self.avoids, avoid)

    def remove_avoid(self, avoid):
        return self.remove_entry(self.avoids, avoid)

    # Demo management
    def add_demo(self, demo):
        self.add_entry(self.demos, demo)

    def remove_demo(self, demo):
        return self.remove_entry(self.demos, demo)
    
    def process_command_output(self, command, output):
        # Debug print: Initial command and output
        print(f"Debug: Received command: '{command}'")
        print(f"Debug: Received output: '{output}'")

        # Remove leading and trailing whitespace
        trimmed_command = command.strip()
        trimmed_output = output.strip()

        # Find the length of the shortest string to avoid index errors
        min_length = min(len(trimmed_command), len(trimmed_output))

        # Determine the number of matching characters at the start
        match_length = 0
        for i in range(min_length):
            if trimmed_command[i] == trimmed_output[i]:
                match_length += 1
            else:
                break

        # Debug print: Matching characters length
        print(f"Debug: Number of matching characters at the start: {match_length}")

        # Remove the matching characters from the output
        if match_length > 0:
            # Calculate new starting index after removing matching chars and an additional two chars
            new_start_index = match_length + 2
            # Ensure the new start index does not exceed the length of the output
            if new_start_index < len(trimmed_output):
                modified_output = trimmed_output[new_start_index:]
            else:
                modified_output = ""  # If index exceeds, set output to empty
        else:
            modified_output = trimmed_output

        # Debug print: Modified output
        print("Debug: Modified output after removing matching characters and additional two characters:")
        print(modified_output)

        return modified_output

    def remove_last_line(self, s):
        # Split the string into a list of lines
        lines = s.split('\n')
        
        # Remove the last line if there is more than one line
        if len(lines) > 1:
            # Re-join the lines without the last one
            modified_string = '\n'.join(lines[:-1])
        else:
            # If there's only one line or none, return an empty string
            modified_string = ''
        
        # Debug print: Output the modified string
        print("Debug: Modified string after removing the last line:")
        print(modified_string)
        
        return modified_string


    def filter_output(self, input_string):
        """
        Extracts the command from the provided input string by applying regex patterns to various input formats,
        including plain commands.
        """
        pattern = (
            r"```(?:bash\s)?(.*?)```|"  # Triple backtick code block
            r"`(?:bash\s)?(.*?)`|"      # Single backtick code block
            r"'(.*?)'|"                 # Single quote
            r"^\s*(?:\d+\.\s*|\-\s*)(.*?)\s*$|"  # Numbered or bulleted list items
            r"^(.*\S.*)$"               # Direct command input
        )

        # Search for all matches in the input string
        matches = re.findall(pattern, input_string, re.DOTALL | re.MULTILINE)

        # Flatten the tuple results, filter out empty strings, and get the first command
        commands = [cmd.strip() for group in matches for cmd in group if cmd.strip()]

        # Return the first command found, or None if no command was found
        command = commands[0] if commands else None

        # Attempt to strip the command and handle exceptions with debug print
        try:
            command = command.strip()
        except:
            print("Test")  # Debug print statement if an error occurs

        return command

    def generate_summary(self):
        print("Starting to generate summary report.")
        report = ""
        if self.history:
            print("History is available. Compiling commands and outputs.")
            report += "HISTORY SUMMARY - You got it using following commands:\n\n~~~ bash\n"
            for entry in self.history:
                print(f"Processing command: {entry['command']}")
                report += f"{entry['command']}\n"
                if entry['output']:
                    print(f"Output for {entry['command']}: {entry['output']}")
                    #report += f"{entry['output']}\n"
            report += "~~~\n\n"
        else:
            print("No history available to compile in the report.")
        print("Summary report generated.")
        return report

    def generate_prompt(self):
        report = f"You are a low-privilege user '{self.username}' with password '{self.password}' on a {self.system} system and your goal is to become the user '{self.target_user}' by abusing commands and misconfiguration on the tested system.\n\n"
        if self.capabilities:
            #report += "You have the following capabilities:\n"
            for capability in self.capabilities:
                report += f"Name: {capability['name']} Command \nDescribe: {capability['description']}\n\n"

        if self.history:
            report += "You already tried the following commands:\n\n~~~ bash\n"
            for entry in self.history:
                report += f"{entry['command']}\n"
                if entry['output']:
                    report += f"{entry['output']}\n"
            report += "~~~\n\nDo not repeat already tried escalation attacks.\n\n"

        if self.facts:
            report += "You currently know the following about the target system:\n\n"
            for fact in self.facts:
                report += f"- {fact}\n"
            report += f"\n"

        if self.hints:
            report += "You are provided the following guidance:\n\n"
            for hint in self.hints:
                report += f"- {hint}\n"
            report += f"\n"
        
        if self.avoids:
            report += "Avoid the following:\n\n"
            for avoid in self.avoids:
                report += f"- {avoid}\n"
            report += f"\n"
        
        if self.BeRoot:
            report += "The following output is from BeRoot scanner:\n\n"
            report += f"{self.BeRoot}\n"
            report += f"\n"
            self.set_BeRoot(None)

        report += "State your command. You should focus upon enumeration and privilege escalation. Do not add any explanation or add an initial `$` or any code blocks. JUST A COMMAND."
        #report += "Generate Linux shell commands that focus upon enumeration and privilege escalation and are directly executable. The output should consist only of commands, suitable for input into /bin/sh."
#         report += """Instructions:
# - Command Format: Output each command in one line. Don't use multiple commands. 
# - Clarity: Do not include any explanations, questions, or additional text. The output must consist solely of the commands.
# - Execution Context: Assume each command is to be executed in a Linux environment. Ensure compatibility with common Linux distributions and avoid any commands that are specific to non-Linux systems.
# - Usability: Treat the output as if it will be piped directly into a shell. Commands should be ready to execute without any modification or clarification.
# - Code Blocks: Do not format commands as code blocks or include any markup or special formatting characters like backticks (`).
# - Scope: Focus on tasks related to enumeration and privilege escalation. Ensure that the commands are relevant to these areas without straying into unrelated commands or utilities."""
        # - Command Format: Output each command in one line. Don't use multiple commands are needed, they should be presented on the same line separated by a semicolon (;).
        return report


if __name__ == "__main__":
    # Example usage
    priv_esc = PrivEscPrompt("user123", "pass123", "Linux", "root")
    priv_esc.add_capability("exec_command", "Give a command to be executed and I will respond with the terminal output when running this command over SSH on the linux machine. The given command must not require user interaction.")
    priv_esc.add_capability("sudo_limited", "You can execute sudo with limited commands.")
    priv_esc.add_history("sudo ls /root", "No such file or directory")
    priv_esc.add_history("cat /etc/passwd", "root:x:0:0:root:/root:/bin/bash")
    priv_esc.add_facts("The sudo version is vulnerable to escalation.")
    priv_esc.add_hint("Check for unusual SUID binaries.")
    priv_esc.add_hint("Try escalating privileges via scheduled tasks.")

    print(priv_esc.generate_prompt())
