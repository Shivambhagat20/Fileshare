# File Server Performance Analysis

## Summary
This report analyzes the performance characteristics of a file server under varying loads. Tests were conducted using simultaneous clients performing upload operations

## Test Configuration
- **File Sizes Tested:** 10.24KB
- **Concurrent Clients:** 1, 2, 5, 10, 20, 50, 100, 200
- **Operations Tested:** Upload
- **Network:** Standard TCP/IP connection

## Key Findings

![Performance Graph](Figure_1.png)

### 1. Scalability with Client Count

#### Upload Performance degradation
- **1-5 clients** Server performance remained roughly the same
- **10-50 clients** Server performance degraded slightly
- **100 - 200 clients** Server performance starts to degrade exponentially, with a possibility of running into an issue with "too many open files"



### 2. Potential Bottlenecks

1. **Network Bandwidth**

2. **Connection Management**

3. **File descriptor limit**
   - maximum number of file handles that the kernel will allocate
   - Impacts performance during concurrent large file operations
   - Exceeding this limit leads to to an OSError: [Errno 24] Too many open files

## Optimization Recommendations

### Short-term Improvements

1. **Connection Pooling**
   - Having resusable connections between the clients and server(s), rather than having to create a new connection for each request.
2. **Increasing the file descriptor limit**