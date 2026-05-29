// @ts-check

/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: false,
    transpilePackages: [
        '@mui/x-data-grid',
        '@mui/x-data-grid-pro',
        '@mui/x-data-grid-premium',
    ],
}

module.exports = nextConfig