# DNS and DoH Performance Measurement Tool

> **⚠️ Warning:** Currently, this script supports **macOS only**.

## Overview

This repository contains the Python script used in our research paper to measure and compare the performance of traditional DNS and DNS over HTTPS (DoH) across different public DNS resolvers and web browsers.

## Features

- Automated measurement of DNS resolution times and page load times.
- Supports testing with multiple DNS resolvers and browsers.
- Outputs results to a CSV file for analysis.

## Installation

1. **Clone the Repository**:

   ```bash
     git clone https://github.com/Simon-Oliver/dns-performance-11484.git
     cd dns-performance-11484
   ```

2. **Install Required Python Packages**:

   ```bash
   pip install selenium speedtest-cli
   ```

3. **Install Browser Drivers**:

   - Download and install the appropriate drivers for Chrome, Firefox, and Edge. Ensure they are accessible in your PATH.

4. **Clone dnsdiag Repository**:

   ```bash
   git clone https://github.com/farrokhi/dnsdiag.git
   ```

   Ensure the `dnsdiag` directory is in the same directory as the script.

## Usage

Run the script using:

```bash
python3 dns_doh_performance.py
```

The script will perform automated tests and save the results to a CSV file.