#!/bin/zsh
# Gör en enskild kontroll och visar lagret i Stockholmsbutikerna just nu (skickar inga notiser).
cd "$(dirname "$0")"
.venv/bin/python bevakare.py --once
