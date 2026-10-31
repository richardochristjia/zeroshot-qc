export const FPS = 30;

export type Zoom = {
  at: number; // seconds into the scene
  scale: number;
  x: number; // focus point, 0..1 of the frame
  y: number;
};

export type Scene = {
  id: string;
  seconds: number;
  captions: string[];
  recording?: string; // file under public/recordings/
  zoom?: Zoom[];
};

export const SCENES: Scene[] = [
  {
    id: 'hook',
    seconds: 12,
    captions: [
      'Small factories still inspect by eye.',
      'Automated inspection needs thousands of labelled photos per product.',
    ],
  },
  {
    id: 'title',
    seconds: 8,
    captions: ['ZeroShot QC', 'Describe the defect in plain English. No training.'],
  },
  {
    id: 'inspect',
    seconds: 20,
    captions: ['Pick a part. Get a verdict, with the reason.'],
    recording: 'inspect-metal-nut.mov',
    zoom: [
      { at: 0, scale: 1, x: 0.5, y: 0.5 },
      { at: 9, scale: 1, x: 0.5, y: 0.5 },
      { at: 11, scale: 1.5, x: 0.7, y: 0.6 },
    ],
  },
  {
    id: 'flip',
    seconds: 31,
    captions: ['Same image. One sentence. No retraining.'],
    recording: 'screw-flip.mov',
    zoom: [
      { at: 0, scale: 1, x: 0.5, y: 0.5 },
      { at: 8, scale: 1, x: 0.5, y: 0.5 },
      { at: 10, scale: 1.5, x: 0.3, y: 0.5 },
      { at: 20, scale: 1.5, x: 0.3, y: 0.5 },
      { at: 22, scale: 1.5, x: 0.7, y: 0.6 },
    ],
  },
  { id: 'pipeline', seconds: 20, captions: [] },
  {
    id: 'proof',
    seconds: 20,
    captions: ["Detection alone isn't enough. The judge plus a reference image does it."],
  },
  {
    id: 'line',
    seconds: 26,
    captions: ['Point a camera at the line. Every part, inspected.'],
    recording: 'line-mode.mov',
  },
  { id: 'outro', seconds: 13, captions: [] },
];

export const totalFrames = () => SCENES.reduce((n, s) => n + s.seconds, 0) * FPS;
