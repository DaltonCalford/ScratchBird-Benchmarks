#!/usr/bin/env python3
"""
Benchmark Result Submission Module

Submits benchmark results along with system information to the
ScratchBird project server for aggregation and analysis.

Supports:
- Anonymous submission
- Authenticated submission with API key
- Offline mode (save locally for later submission)
- Result validation before submission
"""

import gzip
import hashlib
import json
import os
import platform
import ssl
import sys
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.error import HTTPError, URLError


# Default submission endpoint (to be configured)
DEFAULT_SUBMISSION_URL = "https://benchmarks.scratchbird.io/api/v1/submit"
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass
class SubmissionResult:
    """Result of a submission attempt."""
    success: bool
    submission_id: Optional[str] = None
    message: str = ""
    http_status: Optional[int] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ResultSubmitter:
    """Submits benchmark results to the project server."""
    
    def __init__(
        self,
        api_url: str = DEFAULT_SUBMISSION_URL,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        verify_ssl: bool = True
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Create SSL context
        if verify_ssl:
            self.ssl_context = ssl.create_default_context()
        else:
            self.ssl_context = ssl._create_unverified_context()
    
    def submit(
        self,
        benchmark_results: Dict[str, Any],
        system_info: Dict[str, Any],
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        anonymous: bool = True
    ) -> SubmissionResult:
        """
        Submit benchmark results.
        
        Args:
            benchmark_results: The benchmark test results
            system_info: System information from collector
            tags: Optional tags for categorization
            notes: Optional notes about the run
            anonymous: Whether to submit anonymously
            
        Returns:
            SubmissionResult with status and details
        """
        # Prepare submission payload
        payload = self._prepare_payload(
            benchmark_results=benchmark_results,
            system_info=system_info,
            tags=tags or [],
            notes=notes,
            anonymous=anonymous
        )
        
        # Validate payload
        validation_errors = self._validate_payload(payload)
        if validation_errors:
            return SubmissionResult(
                success=False,
                message="Validation failed",
                errors=validation_errors
            )
        
        # Submit
        try:
            return self._send_request(payload)
        except Exception as e:
            return SubmissionResult(
                success=False,
                message=f"Submission failed: {str(e)}",
                errors=[str(e)]
            )
    
    def submit_from_files(
        self,
        benchmark_file: Path,
        system_info_file: Optional[Path] = None,
        **kwargs
    ) -> SubmissionResult:
        """
        Submit results from JSON files.
        
        Args:
            benchmark_file: Path to benchmark results JSON
            system_info_file: Path to system info JSON (optional)
            **kwargs: Additional arguments for submit()
            
        Returns:
            SubmissionResult
        """
        # Load benchmark results
        try:
            with open(benchmark_file, 'r') as f:
                benchmark_results = json.load(f)
        except Exception as e:
            return SubmissionResult(
                success=False,
                message=f"Failed to load benchmark file: {e}",
                errors=[str(e)]
            )
        
        # Load or collect system info
        if system_info_file and system_info_file.exists():
            try:
                with open(system_info_file, 'r') as f:
                    system_info = json.load(f)
            except Exception as e:
                return SubmissionResult(
                    success=False,
                    message=f"Failed to load system info file: {e}",
                    errors=[str(e)]
                )
        else:
            # Auto-collect system info
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from collectors.system_info import SystemInfoCollector
            
            collector = SystemInfoCollector()
            info = collector.collect_all()
            system_info = asdict(info)
        
        return self.submit(benchmark_results, system_info, **kwargs)
    
    def _prepare_payload(
        self,
        benchmark_results: Dict[str, Any],
        system_info: Dict[str, Any],
        tags: List[str],
        notes: Optional[str],
        anonymous: bool
    ) -> Dict[str, Any]:
        """Prepare the submission payload."""
        # Calculate result fingerprint
        result_fingerprint = self._calculate_fingerprint(benchmark_results)
        
        payload = {
            "submission_version": "1.0",
            "submission_time": datetime.now().isoformat(),
            "anonymous": anonymous,
            "client_info": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "submission_tool_version": "1.0.0"
            },
            "benchmark_results": benchmark_results,
            "system_info": system_info,
            "metadata": {
                "tags": tags,
                "notes": notes,
                "result_fingerprint": result_fingerprint
            }
        }
        
        # Add submitter info if not anonymous and API key provided
        if not anonymous and self.api_key:
            payload["submitter"] = {
                "api_key_hash": hashlib.sha256(self.api_key.encode()).hexdigest()[:16]
            }
        
        return payload
    
    def _validate_payload(self, payload: Dict[str, Any]) -> List[str]:
        """Validate the submission payload."""
        errors = []
        
        # Check required fields
        if "benchmark_results" not in payload:
            errors.append("Missing benchmark_results")
        elif not isinstance(payload["benchmark_results"], dict):
            errors.append("benchmark_results must be an object")
        
        if "system_info" not in payload:
            errors.append("Missing system_info")
        elif not isinstance(payload["system_info"], dict):
            errors.append("system_info must be an object")
        
        # Check result size (limit to 50MB)
        payload_size = len(json.dumps(payload).encode('utf-8'))
        if payload_size > 50 * 1024 * 1024:
            errors.append(f"Payload too large: {payload_size / (1024*1024):.1f}MB (max 50MB)")
        
        # Validate benchmark results structure
        benchmark = payload.get("benchmark_results", {})
        if "metadata" not in benchmark:
            errors.append("benchmark_results missing metadata")
        if "summary" not in benchmark:
            errors.append("benchmark_results missing summary")
        
        # Validate system info structure
        sysinfo = payload.get("system_info", {})
        if "cpu" not in sysinfo:
            errors.append("system_info missing cpu info")
        if "memory" not in sysinfo:
            errors.append("system_info missing memory info")
        
        return errors
    
    def _calculate_fingerprint(self, results: Dict[str, Any]) -> str:
        """Calculate a fingerprint of the results for deduplication."""
        # Create a normalized string representation
        normalized = json.dumps(results, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _send_request(self, payload: Dict[str, Any]) -> SubmissionResult:
        """Send the submission request."""
        # Serialize payload
        json_data = json.dumps(payload).encode('utf-8')
        
        # Compress if large (>1MB)
        if len(json_data) > 1024 * 1024:
            json_data = gzip.compress(json_data)
            headers = {
                'Content-Type': 'application/json',
                'Content-Encoding': 'gzip',
                'Accept': 'application/json'
            }
        else:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        
        # Add API key if available
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        
        # Create request
        req = urllib.request.Request(
            self.api_url,
            data=json_data,
            headers=headers,
            method='POST'
        )
        
        # Send request
        try:
            with urllib.request.urlopen(
                req,
                context=self.ssl_context,
                timeout=self.timeout
            ) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                
                return SubmissionResult(
                    success=True,
                    submission_id=response_data.get('submission_id'),
                    message=response_data.get('message', 'Submission successful'),
                    http_status=response.getcode()
                )
                
        except HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body)
                errors = error_data.get('errors', [error_data.get('message', str(e))])
            except:
                errors = [str(e), error_body[:500]]
            
            return SubmissionResult(
                success=False,
                message=f"HTTP Error {e.code}",
                http_status=e.code,
                errors=errors
            )
            
        except URLError as e:
            return SubmissionResult(
                success=False,
                message=f"Connection error: {e.reason}",
                errors=[str(e.reason)]
            )
        
        except Exception as e:
            return SubmissionResult(
                success=False,
                message=f"Request failed: {str(e)}",
                errors=[str(e)]
            )
    
    def save_for_later(
        self,
        benchmark_results: Dict[str, Any],
        system_info: Dict[str, Any],
        output_dir: Path = Path("./pending-submissions"),
        **kwargs
    ) -> Path:
        """
        Save results locally for later submission (offline mode).
        
        Args:
            benchmark_results: The benchmark test results
            system_info: System information
            output_dir: Directory to save pending submission
            **kwargs: Additional metadata
            
        Returns:
            Path to saved file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fingerprint = self._calculate_fingerprint(benchmark_results)[:8]
        filename = f"submission_{timestamp}_{fingerprint}.json"
        filepath = output_dir / filename
        
        # Prepare payload
        payload = self._prepare_payload(
            benchmark_results=benchmark_results,
            system_info=system_info,
            tags=kwargs.get('tags', []),
            notes=kwargs.get('notes'),
            anonymous=kwargs.get('anonymous', True)
        )
        
        # Save
        with open(filepath, 'w') as f:
            json.dump(payload, f, indent=2)
        
        return filepath
    
    def submit_pending(
        self,
        pending_dir: Path = Path("./pending-submissions"),
        delete_on_success: bool = True
    ) -> List[SubmissionResult]:
        """
        Submit all pending submissions.
        
        Args:
            pending_dir: Directory with pending submissions
            delete_on_success: Whether to delete files after successful submission
            
        Returns:
            List of SubmissionResult for each pending file
        """
        pending_dir = Path(pending_dir)
        if not pending_dir.exists():
            return []
        
        results = []
        
        for filepath in sorted(pending_dir.glob("submission_*.json")):
            print(f"Submitting pending file: {filepath.name}")
            
            try:
                with open(filepath, 'r') as f:
                    payload = json.load(f)
                
                result = self._send_request(payload)
                results.append(result)
                
                if result.success and delete_on_success:
                    filepath.unlink()
                    print(f"  ✓ Submitted and removed")
                elif result.success:
                    print(f"  ✓ Submitted (kept)")
                else:
                    print(f"  ✗ Failed: {result.message}")
                    
            except Exception as e:
                results.append(SubmissionResult(
                    success=False,
                    message=f"Failed to process {filepath}: {e}",
                    errors=[str(e)]
                ))
                print(f"  ✗ Error: {e}")
        
        return results


def interactive_submission():
    """Interactive submission prompt."""
    print("="*60)
    print("ScratchBird Benchmark Result Submission")
    print("="*60)
    print()
    
    # Check for benchmark file
    import glob
    benchmark_files = list(Path(".").glob("results/**/*.json"))
    
    if not benchmark_files:
        print("No benchmark result files found in ./results/")
        benchmark_path = input("Enter path to benchmark results JSON: ").strip()
    else:
        print("Found benchmark result files:")
        for i, f in enumerate(benchmark_files[:10], 1):
            print(f"  {i}. {f}")
        
        if len(benchmark_files) > 10:
            print(f"  ... and {len(benchmark_files) - 10} more")
        
        choice = input("\nSelect file number (or enter path): ").strip()
        
        try:
            idx = int(choice) - 1
            benchmark_path = str(benchmark_files[idx])
        except:
            benchmark_path = choice
    
    benchmark_file = Path(benchmark_path)
    if not benchmark_file.exists():
        print(f"Error: File not found: {benchmark_file}")
        return
    
    # Check for system info
    sysinfo_file = benchmark_file.parent / "system-info.json"
    if not sysinfo_file.exists():
        sysinfo_file = Path("system-info.json")
    
    # Ask for tags
    tags_input = input("\nEnter tags (comma-separated, optional): ").strip()
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]
    
    # Ask for notes
    notes = input("Enter notes (optional): ").strip() or None
    
    # Anonymous?
    anonymous_input = input("\nSubmit anonymously? [Y/n]: ").strip().lower()
    anonymous = anonymous_input in ('', 'y', 'yes')
    
    # Confirm
    print("\n" + "-"*60)
    print("Submission Summary:")
    print(f"  Benchmark file: {benchmark_file}")
    print(f"  System info: {sysinfo_file if sysinfo_file.exists() else 'Auto-collect'}")
    print(f"  Tags: {tags or 'None'}")
    print(f"  Anonymous: {anonymous}")
    print("-"*60)
    
    confirm = input("\nSubmit? [Y/n]: ").strip().lower()
    if confirm not in ('', 'y', 'yes'):
        print("Submission cancelled.")
        return
    
    # Submit
    print("\nSubmitting...")
    submitter = ResultSubmitter()
    
    result = submitter.submit_from_files(
        benchmark_file=benchmark_file,
        system_info_file=sysinfo_file if sysinfo_file.exists() else None,
        tags=tags,
        notes=notes,
        anonymous=anonymous
    )
    
    if result.success:
        print(f"\n✓ Submission successful!")
        if result.submission_id:
            print(f"  Submission ID: {result.submission_id}")
        print(f"  View results at: https://benchmarks.scratchbird.io/r/{result.submission_id}")
    else:
        print(f"\n✗ Submission failed: {result.message}")
        if result.errors:
            for error in result.errors:
                print(f"  - {error}")
        
        # Offer to save for later
        save = input("\nSave for later submission? [Y/n]: ").strip().lower()
        if save in ('', 'y', 'yes'):
            with open(benchmark_file, 'r') as f:
                benchmark_results = json.load(f)
            
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from collectors.system_info import SystemInfoCollector
            
            collector = SystemInfoCollector()
            info = collector.collect_all()
            import dataclasses
            system_info = dataclasses.asdict(info)
            
            saved_path = submitter.save_for_later(
                benchmark_results=benchmark_results,
                system_info=system_info,
                tags=tags,
                notes=notes,
                anonymous=anonymous
            )
            print(f"Saved to: {saved_path}")
            print("Run 'submit-pending' later to submit when online.")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Submit benchmark results to ScratchBird project',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive submission
  %(prog)s
  
  # Submit specific file
  %(prog)s --benchmark results/stress-mysql-20240308.json
  
  # Submit with tags
  %(prog)s --benchmark results/*.json --tags production,aws --notes "Initial run"
  
  # Save for later (offline mode)
  %(prog)s --benchmark results/test.json --save-for-later
  
  # Submit all pending
  %(prog)s --submit-pending
        """
    )
    
    parser.add_argument('--benchmark', '-b', type=Path,
                       help='Path to benchmark results JSON file')
    parser.add_argument('--system-info', '-s', type=Path,
                       help='Path to system info JSON file (auto-collect if not provided)')
    parser.add_argument('--tags', '-t', nargs='+',
                       help='Tags for the submission')
    parser.add_argument('--notes', '-n',
                       help='Notes about the benchmark run')
    parser.add_argument('--anonymous', '-a', action='store_true', default=True,
                       help='Submit anonymously (default)')
    parser.add_argument('--identified', '-i', action='store_false', dest='anonymous',
                       help='Submit with identification (requires API key)')
    parser.add_argument('--api-key', '-k',
                       help='API key for authenticated submission')
    parser.add_argument('--api-url', '-u', default=DEFAULT_SUBMISSION_URL,
                       help=f'Submission API URL (default: {DEFAULT_SUBMISSION_URL})')
    parser.add_argument('--save-for-later', action='store_true',
                       help='Save for offline submission instead of submitting now')
    parser.add_argument('--submit-pending', action='store_true',
                       help='Submit all pending submissions')
    parser.add_argument('--pending-dir', type=Path, default=Path('./pending-submissions'),
                       help='Directory for pending submissions')
    
    args = parser.parse_args()
    
    # Handle submit pending
    if args.submit_pending:
        submitter = ResultSubmitter(api_url=args.api_url, api_key=args.api_key)
        results = submitter.submit_pending(args.pending_dir)
        
        success_count = sum(1 for r in results if r.success)
        print(f"\nSubmitted {success_count}/{len(results)} pending submissions")
        return
    
    # Interactive mode if no file specified
    if not args.benchmark:
        interactive_submission()
        return
    
    # Validate file exists
    if not args.benchmark.exists():
        print(f"Error: Benchmark file not found: {args.benchmark}")
        sys.exit(1)
    
    # Create submitter
    submitter = ResultSubmitter(
        api_url=args.api_url,
        api_key=args.api_key
    )
    
    # Submit or save for later
    if args.save_for_later:
        # Load files
        with open(args.benchmark, 'r') as f:
            benchmark_results = json.load(f)
        
        if args.system_info and args.system_info.exists():
            with open(args.system_info, 'r') as f:
                system_info = json.load(f)
        else:
            # Auto-collect
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from collectors.system_info import SystemInfoCollector
            
            collector = SystemInfoCollector()
            info = collector.collect_all()
            import dataclasses
            system_info = dataclasses.asdict(info)
        
        saved_path = submitter.save_for_later(
            benchmark_results=benchmark_results,
            system_info=system_info,
            tags=args.tags,
            notes=args.notes,
            anonymous=args.anonymous
        )
        print(f"Saved for later submission: {saved_path}")
        print(f"Run with --submit-pending to submit when online.")
    else:
        # Submit now
        result = submitter.submit_from_files(
            benchmark_file=args.benchmark,
            system_info_file=args.system_info,
            tags=args.tags,
            notes=args.notes,
            anonymous=args.anonymous
        )
        
        if result.success:
            print(f"✓ Submission successful!")
            if result.submission_id:
                print(f"  Submission ID: {result.submission_id}")
        else:
            print(f"✗ Submission failed: {result.message}")
            if result.errors:
                for error in result.errors:
                    print(f"  - {error}")
            sys.exit(1)


if __name__ == '__main__':
    main()
