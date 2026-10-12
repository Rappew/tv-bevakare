#!/bin/zsh
# Startar bevakaren i bakgrunden. caffeinate hindrar Macen från att somna medan den kör.
cd "$(dirname "$0")"
if [[ -f bevakare.pid ]] && kill -0 "$(cat bevakare.pid)" 2>/dev/null; then
  echo "Bevakaren kör redan (PID $(cat bevakare.pid)). Stoppa med ./stop.sh"
  exit 1
fi
nohup caffeinate -is .venv/bin/python bevakare.py > /dev/null 2>> bevakare.out &
echo $! > bevakare.pid
echo "Bevakaren startad (PID $!). Logg: ./logg.sh   Stoppa: ./stop.sh"
