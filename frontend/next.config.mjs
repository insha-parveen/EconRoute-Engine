/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // No rewrites/proxy needed: the gateway serves CORS "*" and the browser calls
  // NEXT_PUBLIC_API_URL directly. WebSockets are not subject to CORS.
};

export default nextConfig;
