import movementRoutes from "../data/movementRoutes.json"
import type { TechniqueTerm } from "./types"

export const gyms = [
  {
    name: "Movement Fishtown",
    place: "North District",
    count: 1 + movementRoutes.length,
  },
  { name: "Gym B", place: "West District", count: 0 },
]

export const routes = [
  {
    gym: "Movement Fishtown",
    id: "r1",
    name: "Corner Study",
    grade: "V3",
    version: "Set 02",
    archived: false,
  },
  ...movementRoutes,
]

export const similarClimbers = [
  {
    id: "b1",
    name: "Nora P.",
    height: 170,
    wingspan: 172,
    cue: "Right foot before the cross-through",
    time: "0:32",
    bio: "Static climber · prefers controlled movement",
  },
  {
    id: "b2",
    name: "Sam K.",
    height: 166,
    wingspan: 170,
    cue: "Lower hip position through the reach",
    time: "0:19",
    bio: "Dynamic climber · compact reach",
  },
  {
    id: "b3",
    name: "Jo M.",
    height: 174,
    wingspan: 176,
    cue: "Different start point for the same move",
    time: "0:16",
    bio: "",
  },
]

export const betaCards = [
  {
    id: "b1",
    author: "Nora P.",
    gym: "Movement Fishtown",
    route: "Corner Study",
    grade: "V3",
  },
]

export const techniqueTerms: Record<string, TechniqueTerm> = {
  "drop knee": {
    definition:
      "Rotate one knee inward and lower it to bring the hips closer to the wall.",
    use: "Useful when a side-on body position can reduce the reach distance.",
  },
  "inside edge": {
    definition:
      "Place the inside edge of the climbing shoe on a hold for controlled pressure.",
    use: "Useful for stable footwork while rotating the hips toward the wall.",
  },
  flag: {
    definition:
      "Extend a free leg across or behind the body to counterbalance movement.",
    use: "Useful when only one foot is weighted and the body begins to swing.",
  },
}

export const signedDifference = (value: number) =>
  `${value > 0 ? "+" : ""}${value}`

export const routeLabel = (idOrName: string) => {
  const route = routes.find(
    (route) => route.id === idOrName || route.name === idOrName,
  )
  return route ? `${route.gym} · ${route.grade}` : idOrName
}

export const mediaPath = (name: string) =>
  `${import.meta.env.BASE_URL}media/${name}`

export const routeMedia = (id: string) => {
  const photo = movementRoutes.find((route) => route.id === id)
  if (photo) {
    const image = `${import.meta.env.BASE_URL}${photo.image}`
    return { video: "", poster: image, wall: image, pose: null }
  }
  const trial = id === "r1" ? 2 : id === "r2" ? 3 : 1
  return {
    video: mediaPath(`trial${trial}.mp4`),
    poster: mediaPath(`trial${trial}-poster.jpg`),
    wall: mediaPath(`wall${trial}.jpg`),
    pose: trial === 1 ? null : mediaPath(`pose${trial}.mp4`),
  }
}
