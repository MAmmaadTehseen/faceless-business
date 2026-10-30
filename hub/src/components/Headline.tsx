import { duration } from '@/lib/motion';
export default function Headline({text}: {text:string}) {
  return <>{text.split(' ').map((word,i)=><span className="headline-word" key={i} style={{animationDelay:`${i * 25}ms`,animationDuration:`${duration.reveal}s`}}>{word}{' '}</span>)}</>;
}
