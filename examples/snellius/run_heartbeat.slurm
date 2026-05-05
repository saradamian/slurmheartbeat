#!/bin/bash
#SBATCH --job-name=slurmheartbeat
#SBATCH --partition=thin
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00
#SBATCH --output=$HOME/logs/slurmheartbeat/heartbeat.out
#SBATCH --error=$HOME/logs/slurmheartbeat/heartbeat.err

# Slurm Heartbeat test job for Snellius
# NOTE: This is for TESTING ONLY. For production, use screen/tmux or nohup
# because Slurm jobs terminate when walltime expires.

# Load software environment
module load 2025
module load Python/3.11.6

# Activate virtual environment
source $HOME/slurmheartbeat/venv/bin/activate

# Create log directory if it doesn't exist
mkdir -p $HOME/logs/slurmheartbeat

# Run Slurm Heartbeat
echo "Starting Slurm Heartbeat at $(date)"
echo "Config: $HOME/.slurm/heartbeat/config.yaml"
echo ""

python -m slurmheartbeat \
    --config $HOME/.slurm/heartbeat/config.yaml \
    --mode both \
    --verbose

echo ""
echo "Slurm Heartbeat stopped at $(date)"
