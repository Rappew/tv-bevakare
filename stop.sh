#!/bin/zsh
# Stoppar bevakaren (och caffeinate, så att Macen kan somna igen).
cd "$(dirname "$0")"
if [[ -f bevakare.pid ]] && kill -0 "$(cat bevakare.pid)" 2>/dev/null; then
  pid=$(cat bevakare.pid)
  pkill -TERM -P "$pid" 2>/dev/null   # själva Python-programmet
  sleep 2
  kill "$pid" 2>/dev/null             # caffeinate
  rm -f bevakare.pid
  echo "Bevakaren stoppad."
else
  rm -f bevakare.pid
  echo "Bevakaren körs inte."
fi
