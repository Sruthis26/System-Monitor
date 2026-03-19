## Project 1 — System Monitoring Dashboard
 
### Overview
A real-time system health dashboard that tracks CPU, RAM, and disk usage with live charts, threshold-based alerting, and a top-process table — all accessible from a browser.
 
### Tech Stack
`Python` `Flask` `Chart.js` `psutil` `REST API`
 
### Features
- Live CPU, RAM, Disk gauges updating every 5 seconds
- Threshold alerts — CPU >85%, RAM >90%, Disk >80%
- Rolling 60-sample line charts (last 5 minutes of history)
- Top 10 processes by CPU usage
- Structured alert log for post-incident review
- Single-file, no external assets needed
