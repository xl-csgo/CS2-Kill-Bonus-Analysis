# CS2 Kill Bonus Analysis - Docker Setup

This repository contains a comprehensive analysis tool for CS2 demo files that tracks bonus events, equipment purchases, kills, and utility usage.

## Docker Usage

### Prerequisites

- Docker and Docker Compose installed
- CS2 demo files (.dem) placed in the `./demos/` directory

### Quick Start

1. **Place your demo files**:

   ```bash
   # Ensure your .dem files are in the demos directory
   ls ./demos/*.dem
   ```

2. **Run the analysis**:

   ```bash
   docker-compose up --build
   ```

3. **Alternative - Run with Docker directly**:

   ```bash
   # Build the image
   docker build -t cs2-analysis .

   # Run the container with volume mounts
   docker run --rm \
     -v $(pwd)/demos:/app/demos:ro \
     -v $(pwd)/bonus_analysis:/app/bonus_analysis \
     -v $(pwd)/equipment_analysis:/app/equipment_analysis \
     -v $(pwd)/kills_analysis:/app/kills_analysis \
     -v $(pwd)/utility_analysis:/app/utility_analysis \
     -v $(pwd)/combined_analysis:/app/combined_analysis \
     cs2-analysis
   ```

### Volume Mounts Explained

- `./demos:/app/demos:ro` - Mount demo files as read-only
- `./bonus_analysis:/app/bonus_analysis` - Bonus event analysis results
- `./equipment_analysis:/app/equipment_analysis` - Equipment purchase analysis
- `./kills_analysis:/app/kills_analysis` - Kill analysis with purchased weapons
- `./utility_analysis:/app/utility_analysis` - Utility impact analysis
- `./combined_analysis:/app/combined_analysis` - Combined comprehensive report

### Output

After running, you'll find analysis results in:

- `./bonus_analysis/` - JSON files with bonus event data
- `./equipment_analysis/` - Equipment purchase tracking
- `./kills_analysis/` - Kill analysis with purchased weapons
- `./utility_analysis/` - Utility impact analysis
- `./combined_analysis/` - Comprehensive combined report with executive summary

### Example Output Structure

```
bonus_analysis/
├── Team_A_vs_Team_B_map_ESL.json
├── ...

equipment_analysis/
├── Team_A_vs_Team_B_map_ESL_equipment_analysis.json
├── ...

kills_analysis/
├── Team_A_vs_Team_B_map_ESL_kills_analysis.json
├── ...

utility_analysis/
├── Team_A_vs_Team_B_map_ESL_utility_analysis.json
├── ...

combined_analysis/
├── combined_analysis_YYYYMMDD_HHMMSS.json
```

### Troubleshooting

1. **Permission issues**: Make sure the output directories are writable
2. **No demo files**: Ensure .dem files are in `./demos/` directory
3. **Build failures**: Check that requirements.txt contains correct package versions

### Manual Analysis Steps

The analysis runs in this order:

1. **Bonus Analysis** - Find CT team money bonus events (50-250 range)
2. **Equipment Analysis** - Track equipment purchases after bonus events
3. **Kills Analysis** - Analyze kills made with purchased weapons
4. **Utility Analysis** - Analyze utility impact with purchased items
5. **Combined Report** - Generate comprehensive analysis with statistics

Each step builds on the previous one, so all phases must complete successfully for the full analysis.
