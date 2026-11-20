// Concurrent smoke check for the read-only design handoff, including its write boundary.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

type metrics struct {
	Project   string
	Commit    string
	Viewports int
	Tokens    int
	Failures  int `json:"layout_failures"`
}
type sample struct {
	Method string `json:"method"`
	Path   string `json:"path"`
	Status int    `json:"status"`
	Millis int64  `json:"ms"`
	Valid  bool   `json:"valid"`
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "Usage: probe URL expected-game-commit")
		os.Exit(2)
	}
	client := http.Client{Timeout: 10 * time.Second}
	cases := []struct {
		method, path string
		want         int
	}{{"GET", "/metrics", 200}, {"GET", "/", 200}, {"GET", "/metrics", 200}, {"POST", "/metrics", 405}, {"GET", "/unknown", 404}}
	results := make(chan sample, len(cases))
	for _, c := range cases {
		go func(method, path string, want int) {
			start := time.Now()
			record := sample{Method: method, Path: path}
			defer func() { record.Millis = time.Since(start).Milliseconds(); results <- record }()
			req, err := http.NewRequest(method, os.Args[1]+path, nil)
			if err != nil {
				return
			}
			resp, err := client.Do(req)
			if err != nil {
				return
			}
			defer resp.Body.Close()
			record.Status = resp.StatusCode
			body, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
			if err != nil || record.Status != want {
				return
			}
			if path == "/metrics" && method == "GET" {
				var m metrics
				if json.Unmarshal(body, &m) != nil || m.Commit != os.Args[2] || m.Viewports != 7 || m.Project == "" || m.Tokens <= 0 || m.Failures != 0 {
					return
				}
			}
			if path == "/" && !strings.Contains(string(body), "data-component=") {
				return
			}
			record.Valid = true
		}(c.method, c.path, c.want)
	}
	samples := make([]sample, 0, len(cases))
	ok := true
	for range cases {
		s := <-results
		samples = append(samples, s)
		ok = ok && s.Valid
	}
	if err := json.NewEncoder(os.Stdout).Encode(samples); err != nil || !ok {
		os.Exit(1)
	}
}
