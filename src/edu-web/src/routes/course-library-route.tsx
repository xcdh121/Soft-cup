import { CourseLibraryPage } from '@/features/course-library/course-library-page'
import { courseLibraryRoute } from '@/routes/_config'

export const CourseLibraryRoute = () => {
  const search = courseLibraryRoute.useSearch()

  return <CourseLibraryPage initialCourseId={search?.courseId} />
}
