# LRO parameter deployment

`deploy_motorlro_params.py` is the motion-team script supplied for RP025 on
2026-11-04. Its parameter tables, protocol encoding, write/readback sequence and
parallel interface behavior are retained. The integration removes
`start_new_session=True` from per-interface workers so the TUI executor can stop
the entire process group on timeout, including cansend/candump descendants.
The supplied original outside this repository is unchanged.

RP025 validates targets before invoking the script, archives the selected
robot.yaml as an immutable input for this run, and passes explicit can0-can3
interface filters. It reports the script exit status and saves all output.
The script writes CAN_TIMEOUT=0 and Pn parameters; it requires can-utils and
motor firmware supporting the V109+ Pn commands. After successful deployment,
power-cycle the motors as instructed by the motion team.

On TUI 1.1.3 and later, RP025 holds the shared maintenance control lock while
the deployment script runs. It remains board-only and is excluded from the
generic x86 catalog. Per-serial acceptance reporting is handled by the executor.
