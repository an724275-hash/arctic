const widths = {
  '/assets/arctic-coast.webp':1536,
  '/assets/arctic-landscape.webp':1600,
  '/assets/polar-bear-photo.webp':1280,
  '/assets/sea-ice-photo.webp':1280,
};

export function imageSet(photo) {
  return widths[photo] ? `${photo.replace('.webp','-mobile.webp')} 720w, ${photo} ${widths[photo]}w` : '';
}
