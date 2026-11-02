// Prevent Next from opening local environment files during isolated visual QA.
const Module = require('module');
const original = Module._load;
Module._load = function(name, ...args) {
  const value = original.call(this, name, ...args);
  if (name === '@next/env' || name.endsWith('/@next/env/dist/index.js')) return {...value, loadEnvConfig: () => ({combinedEnv: process.env, parsedEnv: {}, loadedEnvFiles: []})};
  return value;
};
