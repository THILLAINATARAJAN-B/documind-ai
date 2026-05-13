// Production environment
// Replace apiUrl with your actual production backend URL
export const environment = {
  production: true,
  // In Docker: backend service is accessible via the docker network name
  // If using nginx proxy: set to '' (empty string, uses relative /api/... paths)
  // If deploying to a domain: set to 'https://api.yourdomain.com'
  apiUrl: '',
};
