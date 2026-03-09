# System Information Collection & Result Submission

Collects comprehensive system information and submits benchmark results to the ScratchBird project.

## Overview

This module provides:
- **System Information Collection** - Hardware, OS, and environment details
- **Result Submission** - Upload benchmark results to project server
- **Offline Mode** - Save results locally for later submission

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

### Submit Benchmark Results

```bash
# Interactive mode
python3 system-info/submit/result_submitter.py

# Submit specific result
python3 system-info/submit/result_submitter.py \
  --benchmark results/stress-mysql-20240308.json \
  --system-info system-info.json \
  --tags production,aws \
  --notes "Initial benchmark run"

# Anonymous submission (default)
python3 system-info/submit/result_submitter.py \
  --benchmark results/*.json \
  --anonymous

# Authenticated submission
python3 system-info/submit/result_submitter.py \
  --benchmark results/*.json \
  --api-key YOUR_API_KEY \
  --identified
```

### Integrated with Test Runner

```bash
# Run tests with system info collection and submission
SUBMIT=true ./run-all-tests.sh all all

# With tags and notes
SUBMIT=true TAGS="production,aws,r5.xlarge" NOTES="First run on new instance" \
  ./run-all-tests.sh stress mysql

# With API key for authenticated submission
SUBMIT=true API_KEY=sb_api_xxx ./run-all-tests.sh all all
```

## Output Format

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

## Offline Mode

If you're running benchmarks offline or submission fails:

```bash
# Save for later submission
python3 system-info/submit/result_submitter.py \
  --benchmark results/test.json \
  --save-for-later

# Submit all pending results when online
python3 system-info/submit/result_submitter.py --submit-pending
```

Pending submissions are saved to `./pending-submissions/` by default.

## API Endpoints

### Submit Results
```http
POST https://benchmarks.scratchbird.io/api/v1/submit
Content-Type: application/json
X-API-Key: your_api_key (optional)

{
  "submission_version": "1.0",
  "submission_time": "2024-03-08T14:30:22",
  "anonymous": true,
  "client_info": { ... },
  "benchmark_results": { ... },
  "system_info": { ... },
  "metadata": {
    "tags": ["production", "aws"],
    "notes": "Initial run",
    "result_fingerprint": "a1b2c3d4"
  }
}
```

### Response
```json
{
  "success": true,
  "submission_id": "sb-sub-12345678",
  "message": "Submission successful",
  "view_url": "https://benchmarks.scratchbird.io/r/sb-sub-12345678"
}
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

### Anonymous Submission
By default, submissions are anonymous. No user identification is stored unless you:
- Provide an API key with `--identified`
- Include identifying information in tags/notes

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

### Submission Fails
1. Check internet connectivity
2. Verify API key if using authenticated submission
3. Save for later: `--save-for-later`
4. Retry with `--submit-pending`

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run benchmarks
  run: ./run-all-tests.sh all all
  env:
    SUBMIT: true
    API_KEY: ${{ secrets.SCRATCHBIRD_API_KEY }}
    TAGS: "ci,github-actions,${{ matrix.os }}"

- name: Upload results on failure
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: benchmark-results
    path: results/
```

### GitLab CI
```yaml
benchmark:
  script:
    - ./run-all-tests.sh all all
  variables:
    SUBMIT: "true"
    API_KEY: $SCRATCHBIRD_API_KEY
    TAGS: "ci,gitlab,production"
```

## License

Same as ScratchBird Benchmarks - IDPL 1.0
