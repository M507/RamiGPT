#!/usr/bin/env python3
"""
Script to generate execution flow diagram for RamiGPT.
Generates both .dot and .svg files showing the flow from user prompt
through AI processing, shell execution, and response handling.
"""

import os
import subprocess
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR

def generate_dot_file():
    """Generate the Graphviz DOT file content."""
    
    dot_content = """digraph RamiGPT_PromptFlow {
    rankdir=LR;
    node [shape=box, style=rounded, fontname="Arial", fontsize=12];
    edge [fontname="Arial", fontsize=11, arrowsize=1.2];
    
    // Main flow nodes
    Start [label="Prompt\\n(generate_prompt)", fillcolor="#E3F2FD", style="filled,rounded"];
    AI [label="AI\\n(OpenAI API)", fillcolor="#F8BBD0", style="filled,rounded"];
    Command [label="Command\\n(filter_output)", fillcolor="#FFF9C4", style="filled,rounded"];
    Shell [label="Shell\\n(SSH Execution)", fillcolor="#FFCCBC", style="filled,rounded"];
    Output [label="Output\\n(shell response)", fillcolor="#C8E6C9", style="filled,rounded"];
    History [label="Add to History\\n(update context)", fillcolor="#E1BEE7", style="filled,rounded"];
    End [label="New Prompt\\n(loop back)", fillcolor="#E3F2FD", style="filled,rounded"];
    
    // Decision point
    RootCheck [label="Root\\nAchieved?", shape=diamond, fillcolor="#FFE0B2", style="filled"];
    
    // Main flow
    Start -> AI [label="Send prompt\\nwith context"];
    AI -> Command [label="AI response\\n(command)"];
    Command -> Shell [label="Execute"];
    Shell -> Output [label="Receive"];
    Output -> History [label="Process"];
    History -> RootCheck;
    RootCheck -> End [label="No\\n(continue)"];
    RootCheck -> Success [label="Yes\\n(success!)", style="bold"];
    End -> Start [label="Generate\\nnew prompt", style="dashed"];
    
    // Success node
    Success [label="Root Access\\nAchieved!", fillcolor="#4CAF50", style="filled,rounded", fontcolor="white"];
    
    // Styling for better layout
    { rank=same; Start; End; }
}
"""
    
    return dot_content

def generate_files():
    """Generate both .dot and .svg files."""
    
    dot_content = generate_dot_file()
    dot_file = OUTPUT_DIR / "execution_flow.dot"
    svg_file = OUTPUT_DIR / "execution_flow.svg"
    
    # Write the DOT file
    print(f"Generating DOT file: {dot_file}")
    with open(dot_file, 'w') as f:
        f.write(dot_content)
    
    # Generate SVG from DOT using Graphviz
    print(f"Generating SVG file: {svg_file}")
    try:
        # Try using 'dot' command (Graphviz)
        subprocess.run(
            ['dot', '-Tsvg', str(dot_file), '-o', str(svg_file)],
            check=True,
            capture_output=True
        )
        print(f"✓ Successfully generated {svg_file}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error generating SVG: {e.stderr.decode()}")
        print("\nNote: Make sure Graphviz is installed.")
        print("Install with: brew install graphviz (macOS) or apt-get install graphviz (Linux)")
        return False
    except FileNotFoundError:
        print("✗ Graphviz 'dot' command not found.")
        print("\nPlease install Graphviz:")
        print("  macOS: brew install graphviz")
        print("  Linux: apt-get install graphviz or yum install graphviz")
        print("  Windows: Download from https://graphviz.org/download/")
        print(f"\nDOT file has been created at: {dot_file}")
        print("You can manually convert it using: dot -Tsvg execution_flow.dot -o execution_flow.svg")
        return False
    
    print(f"\n✓ Files generated successfully:")
    print(f"  - {dot_file}")
    print(f"  - {svg_file}")
    return True

if __name__ == "__main__":
    print("RamiGPT Execution Flow Diagram Generator")
    print("=" * 50)
    generate_files()

