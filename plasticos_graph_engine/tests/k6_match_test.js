import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 50,
  duration: '60s'
};

export default function () {
  const res = http.post('http://localhost:8000/match',
    JSON.stringify({ intake_id: "INT-001" }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(res, {
    'status 200': (r) => r.status === 200,
    'response <150ms': (r) => r.timings.duration < 150
  });
}
