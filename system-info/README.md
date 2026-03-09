# System Information Collection & Report Generation

Collects comprehensive system information and generates human-readable benchmark reports.

## Overview

This module provides:
- **System Information Collection** - Hardware, OS, and environment details
- **Report Generation** - Format benchmark results as readable text files
- **GitHub-Ready Output** - Easy to post to GitHub issues/discussions

## System Information Collected

### Hardware
| Component | Details |
|-----------|---------|
| **CPU** | Model, vendor, cores (physical/logical), frequency, cache, flags, virtualization |
| **GPU** | Vendor, model, VRAM, driver version, CUDA support |
| **Memory** | Total/used/available, type (DDR4/DDR5), speed, channels, swap |
| **Disk** | Device, filesystem, total/free/used, type (SSD/HDD/NVMe) |

### Software
| Component | Details |
|-----------|---------|
| **OS** | Name, version, distribution, kernel, architecture, timezone |
| **Container** | Docker/Podman/Kubernetes detection, cgroup limits |
| **Network** | Hostname, IP, MAC address |
| **Environment** | Relevant environment variables (sanitized) |

## Quick Start

### Collect System Info Only

```bash
# Collect and display
python3 system-info/collectors/system_info.py

# Save to file
python3 system-info/collectors/system_info.py --output my-system.json

# Quiet mode (no display)
python3 system-info/collectors/system_info.py --quiet
```

### Generate Text Reports

```bash
# Interactive mode
python3 system-info/submit/result_formatter.py

# Format a single result
python3 system-info/submit/result_formatter.py \
  --benchmark results/stress-mysql-20240308.json \
  --system-info system-info.json \
  --tags production,aws \
  --notes "Initial benchmark run"

# Compare multiple results
python3 system-info/submit/result_formatter.py \
  --compare results/*.json \
  --system-info system-info.json

# Print to stdout instead of saving
python3 system-info/submit/result_formatter.py \
  --benchmark results/test.json \
  --stdout
```

### Integrated with Test Runner

```bash
# Run tests with system info collection and report generation
REPORT=true ./run-all-tests.sh all all

# With tags and notes
REPORT=true TAGS="production,aws,r5.xlarge" NOTES="First run on new instance" \
  ./run-all-tests.sh stress mysql

# Results saved to: results/full-test-suite-*/reports/
```

## Submitting to GitHub

Benchmark results can be shared by posting to GitHub issues or discussions:

```bash
# 1. Run benchmarks
./run-all-tests.sh all all

# 2. Generate formatted report
python3 system-info/submit/result_formatter.py \
  --benchmark results/acid-firebird-*.json \
  --system-info system-info.json \
  --notes "First test run"

# 3. View the report
cat benchmark_report_firebird_acid_20240308_120000.txt

# 4. Copy contents to clipboard and paste into GitHub:
#    https://github.com/DaltonCalford/ScratchBird-Benchmarks/issues
```

## Output Formats

### System Info JSON

```json
{
  "collection_time": "2024-03-08T14:30:22.123456",
  "platform": "Linux-5.15.0-generic-x86_64",
  "python_version": "3.11.0",
  "cpu": {
    "vendor": "GenuineIntel",
    "model": "Intel(R) Core(TM) i9-12900K",
    "architecture": "x86_64",
    "physical_cores": 16,
    "logical_cores": 24,
    "threads_per_core": 1,
    "base_frequency_mhz": 3200.0,
    "max_frequency_mhz": 5200.0,
    "cache_l1_kb": 1280,
    "cache_l2_kb": 10240,
    "cache_l3_kb": 30720,
    "flags": ["avx", "avx2", "sse4_2", "vm"],
    "virtualization": "VMX capable"
  },
  "gpu": [
    {
      "vendor": "NVIDIA",
      "model": "RTX 3080",
      "vram_mb": 10240,
      "driver_version": "525.60.11",
      "cuda_available": true,
      "cuda_version": "12.0",
      "opencl_available": true
    }
  ],
  "memory": {
    "total_mb": 65536,
    "available_mb": 48123,
    "used_mb": 17413,
    "percent_used": 26.6,
    "type": "DDR5",
    "speed_mhz": 4800,
    "channels": 2,
    "swap_total_mb": 8192,
    "swap_used_mb": 0
  },
  "disks": [
    {
      "device": "/dev/nvme0n1",
      "mount_point": "/",
      "filesystem": "ext4",
      "total_gb": 2048.0,
      "used_gb": 456.3,
      "free_gb": 1591.7,
      "percent_used": 22.3,
      "type": "NVMe SSD",
      "model": "Samsung SSD 980 PRO 2TB",
      "is_rotational": false
    }
  ],
  "os": {
    "name": "Linux",
    "version": "5.15.0",
    "distribution": "Ubuntu 22.04.3 LTS",
    "codename": "jammy",
    "kernel": "5.15.0-92-generic",
    "architecture": "x86_64",
    "timezone": "America/New_York"
  },
  "container": {
    "is_container": false,
    "container_type": "None",
    "is_vm": false,
    "vm_hypervisor": "None",
    "cgroup_limits": {}
  },
  "network": {
    "hostname": "benchmark-server-01",
    "ip_address": "10.0.1.100",
    "mac_address": "aa:bb:cc:dd:ee:ff",
    "interface_name": "eth0",
    "is_wifi": false
  },
  "environment_variables": {
    "HOME": "/home/user",
    "USER": "user",
    "SHELL": "/bin/bash",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "CI": "true",
    "GITHUB_ACTIONS": "true"
  }
}
```

### Text Report Example

```
======================================================================
SCRATCHBIRD BENCHMARK REPORT
======================================================================

BENCHMARK METADATA
----------------------------------------------------------------------
Engine Tested:      firebird
Test Suite:         acid
Timestamp:          2024-03-08T12:00:00
Tags:               production,aws
Notes:              First test run

SYSTEM INFORMATION
----------------------------------------------------------------------
CPU:                Intel(R) Core(TM) i9-12900K
  Vendor:           GenuineIntel
  Physical Cores:   16
  Logical Cores:    24
  Frequency:        3200.0 MHz (base)
  Virtualization:   VMX capable

Memory:             64.0 GB total
  Type:             DDR5 @ 4800 MHz
  Used:             26.6%

Operating System:   Ubuntu 22.04.3 LTS
  Version:          22.04
  Kernel:           5.15.0-92-generic
  Architecture:     x86_64

Storage:
  /dev/nvme0n1:
    Type:           NVMe SSD
    Filesystem:     ext4
    Total:          2048.0 GB
    Free:           1591.7 GB (77.7%)

Environment:        Bare metal

TEST RESULTS
----------------------------------------------------------------------
Total Tests:        20
Passed:             20
Failed:             0
Errors:             0
Score:              100

======================================================================
END OF REPORT
======================================================================

This report was generated by ScratchBird Benchmark Suite.
To submit: Copy this content to a GitHub issue or discussion.
```

## Privacy

### Collected Data
- Hardware specifications (CPU, RAM, disk, GPU)
- Operating system version
- Container/virtualization environment
- Network hostname/IP (for deduplication)
- Environment variables (sanitized)

### Not Collected
- Passwords, secrets, API keys (automatically masked)
- Personal information
- File contents
- Network traffic data

### Sharing Reports
- Reports are plain text - easy to review before sharing
- No automatic uploads or external servers
- You control what gets shared and where

## Requirements

### Python Dependencies
```bash
pip install psutil

# Optional for better Windows support
pip install wmi pywin32

# Optional for better Linux distribution detection
pip install distro
```

### System Requirements
- Python 3.8+
- Read access to:
  - `/proc/cpuinfo` (Linux)
  - `/proc/meminfo` (Linux)
  - `/sys/block/*/queue/rotational` (Linux)
  - System management tools (dmidecode, lspci) - optional

## Troubleshooting

### Permission Denied
Some system information requires elevated permissions:
```bash
sudo python3 system-info/collectors/system_info.py
```

### Missing Information
If certain details are missing:
- Install `dmidecode` for memory type/speed
- Install `lspci` for GPU detection
- Run as root for complete container detection

### Report Generation Fails
1. Check that benchmark JSON files exist
2. Verify system-info.json is present (optional but recommended)
3. Check file permissions on output directory

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run benchmarks
  run: ./run-all-tests.sh all all

- name: Generate reports
  run: |
    python3 system-info/submit/result_formatter.py \
      --compare results/**/*.json \
      --output reports/

- name: Upload results
  uses: actions/upload-artifact@v4
  with:
    name: benchmark-results
    path: |
      results/
      reports/
```

### GitLab CI
```yaml
benchmark:
  script:
    - ./run-all-tests.sh all all
    - python3 system-info/submit/result_formatter.py --compare results/*.json
  artifacts:
    paths:
      - results/
      - reports/
```

## License

Same as ScratchBird Benchmarks - IDPL 1.0
