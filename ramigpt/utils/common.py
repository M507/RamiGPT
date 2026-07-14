
def remove_matching_quotes(s: str) -> str:
    if s and len(s) > 1 and s[0] in "`'\"" and s[0] == s[-1]:
        return s[1:-1]
    return s

def read_file_to_string(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "The file was not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"
