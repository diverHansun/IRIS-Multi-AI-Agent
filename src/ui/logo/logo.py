"""
IRIS Logo Module

This module provides functionality for displaying the IRIS ASCII art logo
with a jasmine light green color theme.
"""

import pyfiglet


JASMINE_GREEN = '\033[38;5;194m'
SCI_FI_BLUE = '\033[38;2;80;180;255m'
RESET = '\033[0m'


def display_logo():
    """
    Generates and prints the IRIS ASCII art logo using pyfiglet with jasmine green coloring.
    """
    # Create Figlet object with the 'block' font for better coloring
    figlet = pyfiglet.Figlet(font='big')
    
    # Generate the ASCII art for "IRIS"
    logo_art_name = figlet.renderText('IRIS').rstrip()
    
    # Print the colored logo
    print(f"{JASMINE_GREEN}{logo_art_name}{RESET}")
  

def display_logo_intro():
    """
    Generates and prints the intro text using pyfiglet with sci-fi blue coloring.
    """
    figlet = pyfiglet.Figlet(font='slant')

    logo_art_intro=figlet.renderText('Muti  AI  Agent')

    print(f"{SCI_FI_BLUE}{logo_art_intro}{RESET}")

# Example usage (if run directly)
if __name__ == "__main__":
    display_logo()
    display_logo_intro()