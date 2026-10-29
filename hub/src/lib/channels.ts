import 'server-only';
import futurework from '../../../channels/futurework/channel.json';
import tradewinds from '../../../channels/tradewinds/channel.json';
import escapevelocity from '../../../channels/escapevelocity/channel.json';

export const channels = [futurework, tradewinds, escapevelocity].map(c => ({
  ...c, color: `rgb(${c.style.accent.join(',')})`,
  links: [
    { label: 'YouTube', url: `https://www.youtube.com/@${c.handle}` },
    { label: 'Instagram', url: `https://www.instagram.com/${c.handle}/` },
    { label: 'Facebook', url: process.env[`HUB_FACEBOOK_URL_${c.key.toUpperCase()}`] },
  ].filter((link): link is {label: string; url: string} => Boolean(link.url)),
}));
export const getChannel = (key: string) => channels.find(c => c.key === key);
