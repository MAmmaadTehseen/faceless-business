const nextConfig = {
  trailingSlash: false,
  devIndicators: false,
  compress: true,
  images: {remotePatterns: [{protocol: 'https', hostname: 'i.ytimg.com', pathname: '/vi/**'}]},
  async headers() { return [
    {source: '/:path*', headers: [
      {key: 'X-Content-Type-Options', value: 'nosniff'},
      {key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin'},
      {key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()'},
      {key: 'Content-Security-Policy', value: "frame-ancestors 'none'; frame-src https://www.youtube-nocookie.com; object-src 'none'; base-uri 'self'"},
    ]},
    {source: '/:path*\\.(woff2|png|jpg|webp|svg)', headers: [{key: 'Cache-Control', value: 'public, max-age=86400'}]},
    {source: '/:icon(favicon\\.ico|favicon\\.svg|favicon-[0-9]+x[0-9]+\\.png|icon-[a-z0-9-]+\\.png|apple-touch-icon\\.png|safari-pinned-tab\\.svg|mark\\.svg)', headers: [{key: 'Cache-Control', value: 'public, max-age=2592000'}]},
  ]; },
};
export default nextConfig;
